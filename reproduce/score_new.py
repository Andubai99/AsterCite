"""Independent explicit semantic review for fresh runs; never calls a model."""
from __future__ import annotations
import argparse,hashlib,json,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"reproduce"))
from scoring import validate_grade,citation_needed
from run import rate
def sha(data):return hashlib.sha256(data).hexdigest()
def read(p):return json.loads(p.read_bytes())
def rows(p):return [json.loads(s) for s in p.read_text(encoding="utf8").splitlines() if s.strip()]
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--run-id",required=True);parser.add_argument("--grade");a=parser.parse_args()
    if not a.run_id or len(a.run_id)>80 or not all(c.isalnum() or c in "_-" for c in a.run_id):raise ValueError("Invalid run ID")
    directory=(ROOT/".local/benchmarks"/a.run_id).resolve()
    if not directory.is_relative_to(ROOT):raise ValueError("Run path escapes project")
    freeze=read(directory/"freeze.json");completion=read(directory/"completion.json")
    if completion["status"]!="finished":raise ValueError("Run still pending")
    cases={c["case_id"]:c for c in rows(ROOT/"reproduce/pipeline/cases.jsonl")}
    entries=[];ledger_files=sorted((directory/"ledger").glob("*.json"));state=read(ledger_files[-1])["state"]
    if len(state["turns"])!=freeze["planned_turns"] or any(t["status"]!="finished" for t in state["turns"]):raise ValueError("Run reservation not terminal")
    for t in state["turns"]:
        path=directory/"turns"/(t["id"]+".json");data=path.read_bytes()
        if sha(data)!=t["result_sha256"]:raise ValueError("Saved result hash differs")
        entries.append((json.loads(data),sha(data)))
    if not a.grade:
        templates=[]
        for e,h in entries:
            if e["record"]["status"]!="completed":continue
            case=cases[e["row"]["case_id"]]
            templates.append({"item_id":e["row"]["item_id"],"outcome_sha256":h,"reviewer_type":"human","reviewer":"","reviewer_relationship":"human",
              "rationale":"","observed_action":None,"requirements":[{"requirement_id":r["requirement_id"],"satisfied":None,"accepted_variant_id":None,"rationale":""} for r in case["answer_requirements"]],
              **{k:None for k in ["action_correct","no_unsupported_claims","user_constraints_correct","query_faithful","intent_behavior_correct","scope_limitations_correct","memory_consistent"]},
              "citation_bindings":[{"citation_id":cid,"supported":None,"rationale":""} for cid in e["record"]["citation_validity"]["cited_ids"]]})
        target=directory/"review-template.json"
        with target.open("x",encoding="utf8") as f:json.dump({"judgements":templates,"status":"pending_explicit_semantic_review"},f,ensure_ascii=False,indent=2)
        index=(ROOT/freeze["config"]["retrieval"]["index_dir"]).resolve()
        if not index.is_relative_to(ROOT):raise ValueError("Index path escapes project")
        chunks={c["chunk_id"]:c for c in rows(index/"chunks.jsonl")}
        history={};materials=[]
        for e,h in entries:
            row=e["row"];record=e["record"];previous=history.setdefault(row["session_key"],[])
            final=next((q for q in record.get("requests",[]) if q["request_id"]==record.get("final_request_id")),{})
            visible={c["chunk_id"] for t in final.get("tool_context",[]) for c in t["visible_chunks"]}
            materials.append({"row":row,"outcome_sha256":h,"answer":record["final_answer"],"actual_history":list(previous),"annotation":cases[row["case_id"]],"actual_visible_sources":[chunks[c] for c in sorted(visible)]})
            previous.append({"question":row["user_text"],"answer":record["final_answer"],"status":record["status"]})
        with (directory/"review-materials.json").open("x",encoding="utf8") as f:json.dump(materials,f,ensure_ascii=False,indent=2)
        print("Review template/materials created. Fill explicit judgements in a copy, then use --grade .local/benchmarks/"+a.run_id+"/review.json");return
    grade_path=(ROOT/a.grade).resolve()
    if not grade_path.is_relative_to(directory):raise ValueError("Review file must be inside this run directory")
    raw=read(grade_path)["judgements"];grades={g["item_id"]:g for g in raw}
    completed={e["row"]["item_id"] for e,h in entries if e["record"]["status"]=="completed"}
    if len(grades)!=len(raw) or set(grades)!=completed:raise ValueError("Every completed output requires exactly one explicit judgement")
    decisions=[]
    for e,h in entries:
        case=cases[e["row"]["case_id"]]
        score=validate_grade(case,e["row"],{"record":e["record"],"sha256":h},grades[e["row"]["item_id"]]) if e["record"]["status"]=="completed" else None
        decisions.append({"case_id":case["case_id"],"engineering_complete":e["record"]["status"]=="completed","task_correct":score["task_correct"] if score else False,"citation_correct":score["citation_correct"] if score else False,"needs_citation":citation_needed(case)})
    result={"mode":"fresh_run_with_explicit_review","n":len(decisions),"plan":{k:freeze[k] for k in ["arm","role","view","planned_turns"]},"completion":rate(d["engineering_complete"] for d in decisions),"task":rate(d["task_correct"] for d in decisions),
      "citations":rate(d["citation_correct"] for d in decisions if d["needs_citation"]),"review_sha256":sha(grade_path.read_bytes()),"reviewer_relationships":sorted({g["reviewer_relationship"] for g in raw}),"per_case":decisions,"actual_billing":"unknown","server_weights_revision":"unknown","provider_calls_during_scoring":0}
    with (directory/"reviewed-results.json").open("x",encoding="utf8") as f:json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!="per_case"},ensure_ascii=False,indent=2))
if __name__=="__main__":main()
