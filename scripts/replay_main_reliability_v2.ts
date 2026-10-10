/** Offline observed-output parsing replay; no API keys, runtime worker or new model request. */
import { readFile, writeFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";
import { parseFullCheck } from "../agent/full-stages.ts";
import { parseFinalAnswer, type AnswerKind } from "../agent/final-answer.ts";
import { parseQuestionPreparation, type PreparationContext } from "../agent/question-preparation.ts";
import { parseCandidateCheck, parseCandidateFinal, parseCandidatePreparation } from "../agent/main-reliability-v2.ts";
import type { Chunk, Paper } from "../agent/contracts.ts";
import type { QuestionFrame } from "../agent/p2-stages.ts";
import type { R2Check } from "../agent/p2-r2.ts";

interface Sample {
  case_id: string; user_text: string; allowed: string[]; frame: QuestionFrame & { intent: string }; public_catalog: Paper[]; preparation_response: string;
  stages: Array<{ stage: string; response: string; status: string; visible: Chunk[]; previous: R2Check | null }>;
  generation: Array<{ response: string; code: string; visible: Chunk[] }>;
}
export async function replayFailures() {
  const packet = JSON.parse(await readFile("tests/evaluation/fixtures/main-c-failures-v2.json", "utf8")) as { fixtures: Sample[]; dependent_cases: string[] };
  const results: Array<{ case_id: string; stage: string; baseline: string; candidate: string; adaptations: string[] }> = [];
  const run = (work: () => unknown) => { try { work(); return "accepted"; } catch (e) { return (e as { code?: string }).code ?? "rejected"; } };
  for (const s of packet.fixtures) {
    const scope = new Set(s.allowed);
    const context: PreparationContext = { original: s.user_text, allowed: scope, publicPapers: s.public_catalog, frameId: "replay/preparation", history: [], activeConstraints: [] };
    const events: string[] = [];
    const baseline = run(() => parseQuestionPreparation(s.preparation_response, context));
    const candidate = run(() => parseCandidatePreparation(s.preparation_response, context, kind => events.push(kind)));
    results.push({ case_id: s.case_id, stage: "preparation", baseline, candidate: events.includes("catalog_query_conflict_original_question_fallback") ? "original_question_fallback" : candidate, adaptations: events });
    let allowAnswer = true;
    for (const stage of s.stages) {
      const evidence = new Map(stage.visible.map(c => [c.chunk_id, c])), previous = stage.previous ?? undefined, adaptations: string[] = [];
      const baseline = run(() => {
        const check = parseFullCheck(stage.response, s.frame, scope, evidence, previous);
        if (stage.status === "completed") allowAnswer = check.checks.every(c => c.status === "supported");
      });
      const candidate = run(() => parseCandidateCheck(stage.response, s.frame, scope, evidence, previous, kind => adaptations.push(kind)));
      results.push({ case_id: s.case_id, stage: stage.stage, baseline, candidate, adaptations });
    }
    const kind: AnswerKind = s.frame.intent === "paper_discovery" ? "catalog" : s.frame.intent === "session_control" ? "session_control" : "paper_fact";
    for (const [i, g] of s.generation.entries()) {
      const evidence = new Map(g.visible.map(c => [c.chunk_id, c])), adaptations: string[] = [];
      results.push({ case_id: s.case_id, stage: `generation_failure_${i + 1}`, baseline: run(() => parseFinalAnswer(g.response, evidence, allowAnswer, Boolean(s.frame.ambiguity), kind)),
        candidate: run(() => parseCandidateFinal(g.response, evidence, allowAnswer, Boolean(s.frame.ambiguity), kind, a => adaptations.push(a))), adaptations });
    }
  }
  return { version: 2, method: "exact_observed_response_and_verified_visible_source_replay", units: "parser_inputs_not_user_turns", results,
    formerly_rejected_now_accepted: results.filter(r => r.baseline !== "accepted" && r.candidate === "accepted").length,
    formerly_accepted_now_rejected: results.filter(r => r.baseline === "accepted" && !["accepted", "original_question_fallback"].includes(r.candidate)).length,
    route_fallbacks: results.filter(r => r.candidate === "original_question_fallback").length,
    dependent_cases: packet.dependent_cases, dependency_recovery: "not_run_no_ideal_history_substitution",
    real_model_requests: 0, semantic_correctness: "not_evaluated", default_reliability: "baseline" };
}
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const report = await replayFailures();
  await writeFile("docs/evidence/main-controls-v2/replay.json", JSON.stringify(report, null, 2) + "\n");
  console.log(JSON.stringify({ recovered_parser_inputs: report.formerly_rejected_now_accepted, parser_regressions: report.formerly_accepted_now_rejected, route_fallbacks: report.route_fallbacks, real_model_requests: 0 }));
}
