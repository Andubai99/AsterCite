"""Offline recomputation from public per-case records and saved semantic judgements."""
from __future__ import annotations
import argparse,collections,hashlib,json,pathlib,sys
from fractions import Fraction
from scoring import validate_grade,citation_needed
ROOT=pathlib.Path(__file__).resolve().parents[1]
ARMS=["A","C","C-no-reflect"]
LABELS=["single_paper_qa","comparison","paper_discovery","scoped_summary","session_control"]
def sha(data):return hashlib.sha256(data).hexdigest()
def canonical(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf8")
def read(root,path):return json.loads((root/path).read_bytes())
def rows(root,path):return [json.loads(l) for l in (root/path).read_text(encoding="utf8").splitlines() if l.strip()]
def rate(values):
    values=list(values);pending=sum(v is None for v in values)
    return {"correct":sum(v is True for v in values),"n":len(values),"pending":pending,"value":None if pending or not values else sum(v is True for v in values)/len(values)}
def classification(pairs):
    confusion={k:{v:0 for v in LABELS+["missing"]} for k in LABELS}
    for gold,pred in pairs:confusion[gold][pred if pred in LABELS else "missing"]+=1
    classes=[]
    for k in LABELS:
        tp=confusion[k][k];support=sum(confusion[k].values());pred=sum(confusion[g][k] for g in LABELS)
        recall=tp/support;precision=tp/pred if pred else 0;f1=2*tp/(support+pred) if support+pred else 0
        classes.append({"label":k,"support":support,"correct":tp,"predicted":pred,"precision":precision,"recall":recall,"f1":f1})
    correct=sum(confusion[k][k] for k in LABELS);available=len(pairs)-sum(confusion[k]["missing"] for k in LABELS)
    return {"n":len(pairs),"correct":correct,"missing":len(pairs)-available,"coverage":available/len(pairs),"accuracy_all":correct/len(pairs),"accuracy_with_prediction":correct/available if available else None,"macro_f1":sum(c["f1"] for c in classes)/5,"classes":classes,"confusion":confusion}
def retrieval_score(case,chunks):
    visible={}
    for c in chunks:visible.setdefault(c["paragraph_id"],set()).update(range(c["start"],c["end"]))
    return max(Fraction(sum(all(set(range(s["start"],s["end"]))<=visible.get(u["paragraph_id"],set()) for s in u["spans"]) for u in g["units"]),len(g["units"])) for g in case["gold_evidence_groups"])
def tokens(record):
    qs=record.get("requests",[])
    if any((q.get("usage") or {}).get("totalTokens") is None for q in qs):return None
    return sum(q["usage"]["totalTokens"] for q in qs)
def paired_tokens(left,right):
    def group(entries):
        g=collections.defaultdict(dict)
        for e in entries:g[e["row"]["session_key"]][e["row"]["turn_index"]]=e["record"]
        return g
    lg,rg=group(left),group(right);pairs=[]
    for sid in sorted(lg.keys()&rg.keys()):
        if set(lg[sid])!={1,2,3,4} or set(rg[sid])!={1,2,3,4}:continue
        records=list(lg[sid].values())+list(rg[sid].values())
        if any(o["status"]!="completed" or tokens(o) is None for o in records):continue
        pairs.append({"session_key":sid,"without_compression_tokens":sum(tokens(o) for o in lg[sid].values()),"compression_recovery_tokens":sum(tokens(o) for o in rg[sid].values())})
    n=len(pairs);l=sum(p["without_compression_tokens"] for p in pairs);r=sum(p["compression_recovery_tokens"] for p in pairs)
    return {"n_paired_dialogues":n,"mean_without_compression_tokens":l/n if n else None,"mean_compression_recovery_tokens":r/n if n else None,"reduction_fraction":1-r/l if l else None,"pairs":pairs,"scope":"same four-turn dialogue; jointly completed; complete totalTokens; includes auxiliary/repair/compaction; descriptive across time periods"}
def replace_failures(original,retries):
    lookup={e["row"]["original_item_id"]:e for e in retries}
    if len(lookup)!=len(retries):raise ValueError("Duplicate retry position")
    if not set(lookup)<=set(original):raise ValueError("Retry outside original compression scope")
    result={}
    for iid,e in original.items():
        if iid in lookup:
            if e["record"]["status"]=="completed":raise ValueError("Successful originals cannot be replaced")
            result[iid]=lookup[iid]
        else:result[iid]=e
    return result
def grade_entries(entries,cases):
    for e in entries:
        if e["record"]["status"]!="completed":
            if e["grade"] is not None or e["historical_scored"] is not None:raise ValueError("Failed outputs cannot receive a semantic success")
            e["scored"]=None;continue
        result=validate_grade(cases[e["row"]["case_id"]],e["row"],{"record":e["record"],"sha256":e["source_outcome_sha256"]},e["grade"])
        if result!=e["historical_scored"]:raise ValueError("Recomputed grade differs from original rule")
        e["scored"]=result
def measure(entries,cases):
    def field(e,k):return False if e["record"]["status"]!="completed" else None if e["scored"] is None else e["scored"][k] is True
    return {"task":rate(field(e,"task_correct") for e in entries),"completion":rate(e["record"]["status"]=="completed" for e in entries),
      "citations":rate(field(e,"citation_correct") for e in entries if citation_needed(cases[e["row"]["case_id"]])),
      "memory":rate(field(e,"memory_consistent") for e in entries if e["row"]["turn_index"]>1),
      "failures":dict(collections.Counter(e["record"].get("failure_code") or "unspecified" for e in entries if e["record"]["status"]!="completed"))}
def control_stats(entries):
    s={"planned_t3":0,"manual_compaction_succeeded":0,"planned_t4":0,"snapshot_revalidated":0,"recovery_answer_completed":0,"automatic_compaction_ends":0}
    for e in entries:
        r=e["row"];o=e["record"]
        s["automatic_compaction_ends"]+=sum(v.get("type")=="end" and v.get("reason") in ("auto","automatic","overflow","threshold") and not v.get("aborted") for v in o.get("compaction_events") or [])
        if r["turn_index"]==3:
            s["planned_t3"]+=1;ctrl=o.get("compaction_control") or {}
            ok=ctrl.get("trigger")=="host_planned" and ctrl.get("natural_settings_restored") is True and any(v.get("type")=="end" and v.get("reason")=="manual" and v.get("aborted") is False for v in o.get("compaction_events") or [])
            if ok and o.get("original_item_id") and not (e.get("native_snapshot_proof") or {}).get("native_compaction_entries"):raise ValueError("Missing actual native summary proof")
            s["manual_compaction_succeeded"]+=ok
        if r["turn_index"]==4:
            s["planned_t4"]+=1;recovered=o.get("session_recovery") or {}
            ok=recovered.get("snapshot_revalidated") is True and recovered.get("recovered_dialogue_turns")==3 and recovered.get("native_compaction_entries",0)>0
            s["snapshot_revalidated"]+=ok;s["recovery_answer_completed"]+=ok and o["status"]=="completed"
    return s
def verify(root=ROOT):
    root=pathlib.Path(root).resolve();manifest=read(root,"reproduce/manifest.json")
    for path,h in manifest["files"].items():
        target=(root/path).resolve()
        if not target.is_relative_to(root) or sha(target.read_bytes())!=h:raise ValueError("Public evidence hash differs: "+path)
    gold={c["case_id"]:c for c in rows(root,"reproduce/retrieval/cases.jsonl")};events=rows(root,"reproduce/retrieval/top5.jsonl")
    expected_retrieval=read(root,"reproduce/retrieval/expected.json");retrieval={}
    registry=read(root,"reproduce/registry.json");retrieval_n=registry["retrieval"]["n"]
    if len(gold)!=retrieval_n or len(events)!=registry["retrieval"]["queries"]:raise ValueError("Retrieval scope differs from the dataset registry")
    for profile in ["dense","bm25","rrf","rrf_rerank"]:
        selected=[e for e in events if e["profile"]==profile]
        if len(selected)!=retrieval_n or {e["case_id"] for e in selected}!=set(gold):raise ValueError("Retrieval case coverage differs")
        scores={e["case_id"]:retrieval_score(gold[e["case_id"]],e["chunks"]) for e in selected}
        for cid,s in scores.items():
            if abs(float(s)-expected_retrieval[profile]["per_case"][cid])>1e-12:raise ValueError("Retrieval per-case score differs")
        average=float(sum(scores.values())/retrieval_n)
        if abs(average-expected_retrieval[profile]["recall_at5"])>1e-12:raise ValueError("Retrieval mean differs")
        retrieval[profile]={"n":retrieval_n,"recall_at5":average}
    cases={c["case_id"]:c for c in rows(root,"reproduce/pipeline/cases.jsonl")};views=read(root,"reproduce/pipeline/views.json")
    original=rows(root,"reproduce/pipeline/original.jsonl");retry=rows(root,"reproduce/pipeline/recovered.jsonl")
    if len(cases)!=295 or len(original)!=1605 or len(retry)!=168:raise ValueError("Agent planned denominators differ")
    grade_entries(original+retry,cases)
    expected=read(root,"reproduce/pipeline/expected.json");primary={};boundaries={};compression={}
    pick=lambda source,arm,role=None,turn=None:[e for e in source if e["row"]["arm"]==arm and (role is None or e["row"]["role"]==role) and (turn is None or e["row"]["turn_index"]==turn)]
    combined=replace_failures({e["row"]["item_id"]:e for e in original if e["row"]["role"]=="compression"},retry)
    selected={e["row"]["original_item_id"] for e in retry}
    affected=[e for e in original if e["row"]["item_id"] in selected]
    if len(affected)!=168 or sum(e["record"]["credit_error_observed"] for e in affected)!=42 or sum(e["record"]["failure_code"]=="DEPENDENCY_FAILED" for e in affected)!=126:
        raise ValueError("Fixed credit/dependency retry selection differs")
    if sum(e["record"]["status"]=="completed" for e in retry)!=expected["retry"]["completed"] or any(e["record"]["credit_error_observed"] for e in retry):
        raise ValueError("Retry terminal counts/provider credit state differ")
    refusal={cid for cid,c in cases.items() if c["expected_action"]=="refuse"};insufficient={cid for cid in refusal if cases[cid]["answerability"]=="not_reported"}
    for arm in ARMS:
        main=pick(original,arm,"main");primary[arm]=measure(main,cases)
        bindings=[]
        for e in main:
            if e["record"]["status"]!="completed":continue
            final=next((q for q in e["record"]["requests"] if q["request_id"]==e["record"]["final_request_id"]),{})
            visible={c["chunk_id"] for t in final.get("tool_context",[]) for c in t["visible_chunks"]}
            bindings.extend(b["supported"] is True and b["citation_id"] in visible for b in e["grade"]["citation_bindings"])
        primary[arm]["citation_binding_support"]=rate(bindings)
        primary[arm]["e2e70"]=measure([e for e in main if e["row"]["case_id"] in views["e2e"]],cases)
        primary[arm]["test177"]=measure([e for e in main if cases[e["row"]["case_id"]]["split"]=="test"],cases)
        def action(ids):return rate(e["record"]["status"]=="completed" and e["scored"] is not None and e["scored"]["action_correct"] is True for e in main if e["row"]["case_id"] in ids)
        b=set(views["boundary"]);boundaries[arm]={"boundary55_action":action(b),"boundary15_refusal":action(b&refusal),"all17_refusal":action(refusal),"evidence_insufficient7_refusal":action(insufficient)}
        before=pick(original,arm,"compression");after=pick(combined.values(),arm);off=pick(original,arm,"native_off")
        compression[arm]={"retry56":measure(pick(retry,arm),cases),"original120":measure(before,cases),"service_recovered120":measure(after,cases),"without_compression120":measure(off,cases),
            "t3":measure(pick(combined.values(),arm,turn=3),cases),"t4":measure(pick(combined.values(),arm,turn=4),cases),"controls":control_stats(after),"paired_tokens":paired_tokens(off,after)}
    for k,v in [("original_main",primary),("boundary_refusal",boundaries),("compression",compression)]:
        if v!=expected[k]:raise ValueError("Recomputed "+k+" differs from preserved historical table")
    classes={};expected_classes=read(root,"reproduce/intent/expected.json")
    lookup={e["row"]["item_id"]:e for e in original}
    for arm in ["C","C-no-reflect"]:
        selected=[lookup["ac295-v6/main/"+arm+"/"+cid] for cid in views["intent"]]
        classes[arm]={name:classification([(cases[e["row"]["case_id"]]["intent"],e["record"]["preparation_labels"][field]) for e in selected]) for name,field in [("raw_model_labels","raw_intent"),("host_accepted_labels","accepted_intent")]}
        if any(classes[arm][name]!=expected_classes[arm][name] for name in classes[arm]):raise ValueError("Classification differs")
    rewrite=read(root,"reproduce/query-rewrite/judgements.json");packets={p["review_id"]:p for p in read(root,"reproduce/query-rewrite/packets.json")["packets"]}
    if len(packets)!=200 or len(rewrite["judgements"])!=200:raise ValueError("Rewrite scope differs")
    for g in rewrite["judgements"]:
        packet=packets[g["review_id"]];e=lookup[g["item_id"]]
        if packet["material_sha256"]!=sha(canonical({k:v for k,v in packet.items() if k!="material_sha256"})) or g["material_sha256"]!=packet["material_sha256"] or g["outcome_sha256"]!=e["source_outcome_sha256"] or packet["rewrite"]!=e["record"]["preparation_labels"]["raw_rewrite"]:raise ValueError("Rewrite grade/source binding differs")
        if g["rewrite_present"]!=(packet["rewrite"] is not None) or g["rewrite_faithful"] and not g["rewrite_present"]:raise ValueError("Missing rewrite cannot pass")
    rewritten={}
    for arm in ["C","C-no-reflect"]:
        gs=[g for g in rewrite["judgements"] if g["arm"]==arm];n=len(gs);present=sum(g["rewrite_present"] for g in gs);correct=sum(g["rewrite_faithful"] is True for g in gs)
        rewritten[arm]={"n":n,"present":present,"missing":n-present,"correct":correct,"accuracy_all":correct/n,"accuracy_with_rewrite":correct/present,"coverage":present/n}
    if rewritten!=expected["query_rewrite"]:raise ValueError("Rewrite aggregate differs")
    return {"status":"verified","provider_calls":0,"retrieval":retrieval,"original_main":primary,"boundary_refusal":boundaries,"classification":classes,"query_rewrite":rewritten,"compression":compression,
        "limits":{"saved_semantic_judgements":True,"independent_human_review":False,"server_weights_revision":"unknown","actual_billing":"unknown"}}
def table(v):
    p=v["original_main"];b=v["boundary_refusal"];c=v["compression"]
    fmt=lambda x:f'{x["value"]*100:.2f}%' if x["value"] is not None else "—"
    out=["# 评测结果","","使用随附评测资料复算。运行方法与数据入口见 [复现指南](../reproduce/README.md)。","","## 检索","","| 配置 | Span Recall@5 |","|---|---:|"]
    for key,name in [("dense","Dense"),("bm25","BM25"),("rrf","Dense + BM25 + RRF"),("rrf_rerank","+ Cross-Encoder 重排")]:
        out.append(f'| {name} | {100*v["retrieval"][key]["recall_at5"]:.2f}% |')
    hybrid=100*(v["retrieval"]["rrf"]["recall_at5"]-v["retrieval"]["dense"]["recall_at5"])
    rerank=100*(v["retrieval"]["rrf_rerank"]["recall_at5"]-v["retrieval"]["rrf"]["recall_at5"])
    out+=["",f"混合检索提升 {hybrid:.2f} 个百分点，重排进一步提升 {rerank:.2f} 个百分点。","","## 问答","","| 指标 | 基础流程 | AsterCite |","|---|---:|---:|"]
    for name,fn in [("任务正确率",lambda a:p[a]["task"]),("流程完成率",lambda a:p[a]["completion"]),("引用支持率",lambda a:p[a]["citation_binding_support"]),("引用完全正确率",lambda a:p[a]["citations"]),("边界动作准确率",lambda a:b[a]["boundary55_action"])]:
        out.append("| "+name+" | "+" | ".join(fmt(fn(a)) for a in ["A","C-no-reflect"])+" |")
    out+=["", "| 多轮理解 | AsterCite |","|---|---:|",
        f'| 意图分类准确率 | {100*v["classification"]["C-no-reflect"]["raw_model_labels"]["accuracy_all"]:.2f}% |',
        f'| Query 改写准确率 | {100*v["query_rewrite"]["C-no-reflect"]["accuracy_all"]:.2f}% |',
        "","## 压缩与恢复","","| 指标 | 基础流程 | AsterCite |","|---|---:|---:|"]
    for name,fn in [("流程完成率",lambda a:c[a]["service_recovered120"]["completion"]),("任务正确率",lambda a:c[a]["service_recovered120"]["task"]),("压缩后记忆一致率",lambda a:c[a]["t3"]["memory"]),("恢复后记忆一致率",lambda a:c[a]["t4"]["memory"])]:
        out.append("| "+name+" | "+" | ".join(fmt(fn(a)) for a in ["A","C-no-reflect"])+" |")
    out.append("| 配对对话 token 减少 | "+" | ".join(f'{100*c[a]["paired_tokens"]["reduction_fraction"]:.2f}%' for a in ["A","C-no-reflect"])+" |")
    out+=["","检索按原文证据跨度评分；问答按任务、流程和引用分别评分。压缩项按配对运行记录统计 token。各指标按对应数据视图统计；语义项采用开发者 AI 标注，详情见复现指南。"]
    return "\n".join(out)+"\n"
if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--write",action="store_true",help="Write a derived table under .local/reproduction");a=parser.parse_args()
    v=verify();text=table(v)
    if a.write:
        directory=ROOT/".local/reproduction";directory.mkdir(parents=True,exist_ok=True)
        (directory/"results.json").write_text(json.dumps(v,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
        (directory/"results.md").write_text(text,encoding="utf8")
    print(text)
