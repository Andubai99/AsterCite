import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";
import { parseFullFrame, parseFullCheck } from "../../agent/full-stages.ts";
import { parseQuestionFrame } from "../../agent/p2-stages.ts";
import { parseR2Check } from "../../agent/p2-r2.ts";
import type { Chunk } from "../../agent/contracts.ts";
import { DomainMemory } from "../../agent/domain-memory.ts";

const source: Chunk = { paper_id: "p1", paragraph_id: "p1:s0:p0", chunk_id: "full:p1:s0:p0:c0-15",
  section: "Results", text: "A😀 real source.", start: 0, end: 15, index_version: "full" };
const allowed = new Set(["p1"]), evidence = new Map([[source.chunk_id, source]]);
const frame = parseQuestionFrame(JSON.stringify({ question_text: "question", candidate_papers: ["p1"], ordered_targets: ["p1"],
  information_needs: ["explain the finding"], queries: [{ query: "finding", paper_ids: ["p1"] }], ambiguity: null, user_constraints: [] }), "question", allowed);
const support = { need_id: "n1", status: "supported", basis: "explicit", finding: "finding paraphrase",
  support_spans: [{ chunk_id: source.chunk_id, quote: source.text }] };

test("full-v1 normalizes six real insufficient responses without changing their old failure or inventing support", async () => {
  const saved = JSON.parse(await readFile("docs/evidence/p2-r2-stage-regressions.json", "utf8"));
  let count = 0;
  for (const sample of saved.cases) {
    const historicalFrame = sample.stages.find((stage: { stage: string }) => stage.stage === "question_frame").value;
    for (const stage of sample.stages.filter((stage: { status: string }) => stage.status === "schema_error")) {
      const scope = new Set<string>(historicalFrame.candidate_papers);
      assert.throws(() => parseR2Check(stage.response_text, historicalFrame, scope, new Map()), /evidence_ids/);
      const normalized = parseFullCheck(stage.response_text, historicalFrame, scope, new Map());
      assert.equal(normalized.next_action, "retrieve_more");
      assert.deepEqual(normalized.checks[0].evidence_ids, []);
      assert.deepEqual(normalized.checks[0].support_spans, []);
      assert.equal(normalized.checks[0].finding, null); count++;
    }
    assert.equal(sample.final_answer, "");
  }
  assert.equal(count, 6);
});

test("supported derives only source IDs and exact Unicode offsets, permitting paraphrased findings", () => {
  const result = parseFullCheck(JSON.stringify({ checks: [support], next_action: "answer" }), frame, allowed, evidence);
  assert.deepEqual(result.checks[0].evidence_ids, [source.chunk_id]);
  assert.equal(result.checks[0].support_spans[0].end, Array.from(source.text).length);
  for (const bad of [{ ...support, support_spans: null }, { ...support, basis: undefined },
    { ...support, evidence_ids: ["fake"] }, { ...support, gap: "contradiction" }]) {
    assert.throws(() => parseFullCheck(JSON.stringify({ checks: [bad], next_action: "answer" }), frame, allowed, evidence));
  }
});

test("insufficient, conflicting and partial branches retain gaps and forbid affirmative answer", () => {
  const gap = { need_id: "n1", status: "insufficient", gap: "Missing required condition" };
  const result = parseFullCheck(JSON.stringify({ checks: [gap], next_action: "refuse" }), frame, allowed, evidence);
  assert.equal(result.checks[0].basis, null);
  assert.throws(() => parseFullCheck(JSON.stringify({ checks: [gap], next_action: "answer" }), frame, allowed, evidence));
  assert.throws(() => parseFullCheck(JSON.stringify({ checks: [{ ...gap, status: "conflicting", evidence_ids: [source.chunk_id] }], next_action: "refuse" }), frame, allowed, evidence));
  const other = { ...source, chunk_id: "second" }, both = new Map([...evidence, [other.chunk_id, other] as [string, Chunk]]);
  assert.equal(parseFullCheck(JSON.stringify({ checks: [{ ...gap, status: "conflicting", evidence_ids: [source.chunk_id, other.chunk_id] }], next_action: "refuse" }), frame, allowed, both).checks[0].status, "conflicting");
});

test("need IDs bind meaning independently of finding text and reject missing/duplicate/unknown IDs", () => {
  for (const checks of [[], [support, support], [{ ...support, need_id: "n999" }]]) {
    assert.throws(() => parseFullCheck(JSON.stringify({ checks, next_action: "answer" }), frame, allowed, evidence));
  }
});

test("new support after a gap needs an actual new exact source span and an explanation", () => {
  const prior = parseFullCheck(JSON.stringify({ checks: [{ need_id: "n1", status: "insufficient", gap: "condition" }], next_action: "refuse" }), frame, allowed, evidence);
  assert.throws(() => parseFullCheck(JSON.stringify({ checks: [support], next_action: "answer" }), frame, allowed, evidence, prior), /gap_resolution/);
  assert.equal(parseFullCheck(JSON.stringify({ checks: [{ ...support, gap_resolution: "new source supplies the condition" }], next_action: "answer" }), frame, allowed, evidence, prior).checks[0].status, "supported");
});

test("NLU host assigns question and ID, uses separate intent/follow-up and binds user constraints to actual input", () => {
  const raw = { intent: "comparison", follow_up: true, candidate_papers: ["p1"], ordered_targets: ["p1"],
    information_needs: ["methods"], queries: [{ query: "method", paper_ids: ["p1"] }],
    constraints: [{ key: "focus", value: "methods", source_quote: "methods", replaces: "focus" }], comparison_dimensions: ["methods"] };
  const parsed = parseFullFrame(JSON.stringify(raw), "Compare methods", allowed, "turn/frame");
  assert.equal(parsed.frame_id, "turn/frame"); assert.equal(parsed.question_text, "Compare methods");
  assert.equal(parsed.information_needs[0].need_id, "n1"); assert.equal(parsed.follow_up, true);
  assert.throws(() => parseFullFrame(JSON.stringify({ ...raw, constraints: [{ key: "focus", value: "x", source_quote: "made up" }] }), "Compare methods", allowed), /constraints\[0\].source_quote/);
  assert.throws(() => parseFullFrame(JSON.stringify({ ...raw, intent: "follow_up" }), "Compare methods", allowed), /intent/);
  assert.throws(() => parseFullFrame(JSON.stringify({ ...raw, queries: [] }), "Compare methods", allowed), /queries/);
});

test("actual ambiguity permits clarification with empty retrieval; illegal query papers and JSON duplicate fields fail", () => {
  const raw = { intent: "single_paper_qa", follow_up: true, ambiguity: "Which of these papers?" };
  assert.equal(parseFullFrame(JSON.stringify(raw), "What about it?", allowed).queries.length, 0);
  assert.throws(() => parseFullFrame(JSON.stringify({ ...raw, queries: [{ query: "it", paper_ids: ["outside"] }] }), "What about it?", allowed));
  assert.throws(() => parseFullCheck('{"checks":[],"checks":[],"next_action":"refuse"}', frame, allowed, evidence), /Duplicate JSON key/);
});

test("branch diagnostics name the actual field, value and violated constraint", () => {
  assert.throws(() => parseFullCheck(JSON.stringify({ checks: [{ need_id: "n1", status: "sure" }], next_action: "answer" }), frame, allowed, evidence), /checks\[0\].status.*sure.*supported/);
});

test("unmodified real Dev2 full-list quotes pass full source bounds and no-prior-gap normalization while legacy R2 stays strict", async () => {
  const saved=JSON.parse(await readFile("docs/evidence/full-project-dev2-stage-regressions-v1.json","utf8"));
  const sample=saved.cases[0], real=sample.stages.find((s:{stage:string})=>s.stage==="evidence_check");
  const evidence=new Map<string,Chunk>(sample.sources.map((c:Chunk)=>[c.chunk_id,c]));
  const scope=new Set<string>(sample.question_frame.candidate_papers);
  const check=parseFullCheck(real.response_text,sample.question_frame,scope,evidence);
  assert.deepEqual(check.checks[0].support_spans.map(s=>[s.start,s.end]),[[0,324],[326,501]]);
  assert.equal(check.checks[0].gap_resolution,null);assert.equal(check.checks[0].status,"supported");
  const raw={...check,checks:check.checks.map(c=>({...c,support_spans:c.support_spans.map(({chunk_id,quote})=>({chunk_id,quote}))}))};
  assert.throws(()=>parseR2Check(JSON.stringify(raw),sample.question_frame,scope,evidence),/span source\/length/);
  for(const bad of ["German",check.checks[0].support_spans[0].quote.replace("German","French")]) {
    const changed=structuredClone(raw);changed.checks[0].support_spans[0].quote=bad;
    assert.throws(()=>parseFullCheck(JSON.stringify(changed),sample.question_frame,scope,evidence),/unique exact substring/);
  }
  assert.throws(()=>parseFullCheck(real.response_text,sample.question_frame,scope,new Map()),/actually visible/);
  assert.throws(()=>parseFullCheck(JSON.stringify({checks:[{...support,gap_resolution:"x".repeat(501)}],next_action:"answer"}),frame,allowed,new Map([[source.chunk_id,source]])),/gap_resolution.*500/);
});

test("full support bounds count Unicode codepoints and remain capped at the actual 2000-codepoint source window",()=> {
  const quote="😀".repeat(1996)+"|end",chunk={...source,text:quote,chunk_id:"full-window",end:2000};
  const check={checks:[{...support,support_spans:[{chunk_id:chunk.chunk_id,quote}]}],next_action:"answer"};
  assert.equal(parseFullCheck(JSON.stringify(check),frame,allowed,new Map([[chunk.chunk_id,chunk]])).checks[0].support_spans[0].end,2000);
  const longer="😀"+quote,bad={...chunk,text:longer,end:2001};
  assert.throws(()=>parseFullCheck(JSON.stringify({checks:[{...support,support_spans:[{chunk_id:chunk.chunk_id,quote:longer}]}],next_action:"answer"}),frame,allowed,new Map([[chunk.chunk_id,bad]])),/quote.*2000/);
});

test("real Dev2 repeated active constraint is a source-verified no-op; altered, stale and unverified history remain illegal",async()=> {
  const saved=JSON.parse(await readFile("docs/evidence/full-project-dev2-stage-regressions-v1.json","utf8"));
  const sample=saved.cases[1],raw=sample.stages.find((s:{stage:string})=>s.stage==="question_frame_format_repair").response_text;
  const context={active_constraints:sample.prior_domain_state.user_constraints,user_history:sample.actual_prior_user_history};
  const scope=new Set<string>(sample.allowed_papers);
  const parsed=parseFullFrame(raw,sample.user_text,scope,"real-follow-up/frame",context);
  assert.deepEqual(parsed.constraints,[]);assert.equal(parsed.inherited_constraints?.length,1);
  assert.equal(parsed.inherited_constraints?.[0].source_turn,sample.actual_prior_user_history[0].turn_id);
  const memory=new DomainMemory(sample.prior_domain_state.index_version,sample.prior_domain_state);
  memory.applyFrame(parsed,"real-follow-up");assert.deepEqual(memory.state.user_constraints,sample.prior_domain_state.user_constraints);
  assert.throws(()=>parseFullFrame(sample.stages[0].response_text,sample.user_text,scope,"wrong-stage",context),/frame.status/);
  for(const changed of [
    {...context,active_constraints:context.active_constraints.map((c:Record<string,unknown>)=>({...c,value:"Chinese"}))},
    {...context,active_constraints:context.active_constraints.map((c:Record<string,unknown>)=>({...c,superseded_by:"newer"}))},
    {...context,user_history:[]},
    {...context,user_history:context.user_history.map((h:Record<string,unknown>)=>({...h,user_text:"fabricated history"}))}
  ])assert.throws(()=>parseFullFrame(raw,sample.user_text,scope,"bad-follow-up",changed),/source_quote.*THIS user input/);
  const value=JSON.parse(raw);
  for(const update of [{...value.constraints[0],value:"Chinese"},{...value.constraints[0],replaces:"answer_language"}])
    assert.throws(()=>parseFullFrame(JSON.stringify({...value,constraints:[update]}),sample.user_text,scope,"bad-change",context),/source_quote.*THIS user input/);
  const corrected=parseFullFrame(JSON.stringify({...value,constraints:[{key:"answer_language",value:"Chinese",source_quote:"Chinese",replaces:"answer_language"}]}),"Correction: Chinese",scope,"correction/frame",context);
  memory.applyFrame(corrected,"correction");assert.equal(memory.activeConstraints()[0].value,"Chinese");assert.equal(memory.activeConstraints()[0].source_turn,"correction");
  assert.equal(memory.state.user_constraints[0].superseded_by,"correction");
});
