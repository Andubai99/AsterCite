"""Run a fresh bounded original47 retrieval comparison in an isolated corpus worker (0 generation calls)."""
from __future__ import annotations
import argparse,datetime,hashlib,json,os,pathlib,queue,subprocess,sys,threading,uuid
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"reproduce"))
from run import retrieval_score
def read(path):return json.loads(path.read_bytes())
def rows(path):return [json.loads(l) for l in path.read_text(encoding="utf8").splitlines() if l.strip()]
def inside(path):
    target=(ROOT/path).resolve()
    if not target.is_relative_to(ROOT):raise ValueError("Path must stay inside project")
    return target
def environment():
    result={"PYTHONUTF8":"1","PYTHONIOENCODING":"utf-8"}
    for k in ["PATH","Path","SystemRoot","SYSTEMROOT","WINDIR","COMSPEC","PATHEXT","TEMP","TMP"]:
        if k in os.environ:result[k]=os.environ[k]
    return result
class Worker:
    def __init__(self,python,index,models,device,profile):
        args=[str(python),str(ROOT/"retriever/worker.py"),"--corpus-dir",str(ROOT/"data/full-v1/corpus"),"--index-dir",str(index),"--models-dir",str(models),"--device",device,"--profile",profile]
        self.process=subprocess.Popen(args,cwd=ROOT,env=environment(),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding="utf8",bufsize=1)
        self.frames=queue.Queue()
        def collect():
            for line in self.process.stdout:self.frames.put(line)
            self.frames.put(None)
        threading.Thread(target=collect,daemon=True).start()
        threading.Thread(target=lambda:list(iter(self.process.stderr.readline,"")),daemon=True).start()
        try:
            ready=self.receive(180)
            if ready.get("type")!="ready":raise ValueError("Worker failed readiness: "+str(ready.get("error",{}).get("code","unknown")))
            self.index_version=ready["index_version"]
        except BaseException:self.close();raise
    def receive(self,timeout=60):
        line=self.frames.get(timeout=timeout)
        if line is None:raise ValueError("Worker exited before responding")
        return json.loads(line)
    def query(self,query,scope):
        request_id=str(uuid.uuid4());self.process.stdin.write(json.dumps({"version":1,"request_id":request_id,"method":"retrieve_chunks","params":{"query":query,"paper_ids":scope,"top_k":5,"allowed_paper_ids":scope}})+"\n");self.process.stdin.flush()
        frame=self.receive()
        if frame.get("request_id")!=request_id:raise ValueError("Worker request identity differs")
        if "error" in frame:raise ValueError("Retrieval failed: "+frame["error"]["code"])
        return frame["result"]["chunks"]
    def close(self):
        self.process.kill();self.process.wait(timeout=10)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--execute",action="store_true");p.add_argument("--run-id");p.add_argument("--limit",type=int,default=47);p.add_argument("--index-dir",default="artifacts/full-v1/pipaper-full-index-v1-e7699c38391f1315");p.add_argument("--models-dir",default=".cache/models");p.add_argument("--device",choices=["cuda","cpu"],default="cuda");a=p.parse_args()
    if not 1<=a.limit<=47:raise ValueError("limit must be 1..47")
    events=rows(ROOT/"reproduce/retrieval47/top5.jsonl");tasks={e["case_id"]:{k:e[k] for k in ["case_id","query","scope"]} for e in events};selected=list(tasks.values())[:a.limit]
    plan={"version":1,"cases":selected,"profiles":["dense","bm25","rrf","rrf_rerank"],"queries":4*a.limit,"provider_calls":0,"device":a.device,"index_dir":a.index_dir,"mode":"fresh_local_retrieval"}
    if not a.execute:print(json.dumps(plan,ensure_ascii=False,indent=2));return
    if not a.run_id or not all(c.isalnum() or c in "_-" for c in a.run_id) or len(a.run_id)>80:raise ValueError("Use an explicit ASCII --run-id")
    directory=inside(".local/retrieval47/"+a.run_id);directory.parent.mkdir(parents=True,exist_ok=True);directory.mkdir()
    index=inside(a.index_dir);models=inside(a.models_dir);python=ROOT/".venv"/("Scripts/python.exe" if os.name=="nt" else "bin/python")
    plan["index_manifest_sha256"]=hashlib.sha256((index/"index-manifest.json").read_bytes()).hexdigest();plan["planned_queries_reserved"]=4*a.limit
    (directory/"freeze.json").write_text(json.dumps(plan,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    gold={c["case_id"]:c for c in rows(ROOT/"reproduce/retrieval47/cases.jsonl")};scores={}
    for profile in plan["profiles"]:
        worker=Worker(python,index,models,a.device,profile);values=[]
        try:
            for task in selected:
                attempt=directory/(profile+"-"+task["case_id"]+".attempt.json")
                attempt.write_text(json.dumps({"reserved":True,"query":task["query"],"index_version":worker.index_version}),encoding="utf8")
                chunks=worker.query(task["query"],task["scope"]);score=retrieval_score(gold[task["case_id"]],chunks);values.append(float(score))
                (directory/(profile+"-"+task["case_id"]+".json")).write_text(json.dumps({**task,"profile":profile,"index_version":worker.index_version,"chunks":chunks,"recall_at5":float(score)},ensure_ascii=False)+"\n",encoding="utf8")
            scores[profile]={"n":len(values),"recall_at5":sum(values)/len(values)};print(profile+" finished "+str(len(values)),flush=True)
        finally:worker.close()
    result={"mode":"fresh_local_retrieval","provider_calls":0,"queries":4*a.limit,"full_original47":a.limit==47,"scores":scores,"index_version":read(index/"index-manifest.json")["index_version"]}
    (directory/"results.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf8");print(json.dumps(result))
if __name__=="__main__":main()
