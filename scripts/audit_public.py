"""Scan publishable source/data only; report file names and counts, never secret contents."""
from __future__ import annotations
import argparse,hashlib,json,os,pathlib,re,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[1]
def candidates(root):
    top=subprocess.run(["git","rev-parse","--show-toplevel"],cwd=root,capture_output=True,text=True)
    result=subprocess.run(["git","-c","core.quotepath=false","ls-files","--cached","--others","--exclude-standard","-z"],cwd=root,capture_output=True)
    if result.returncode==0 and top.returncode==0 and pathlib.Path(top.stdout.strip()).resolve()==root.resolve():
        return sorted({p.decode("utf8") for p in result.stdout.split(b"\0") if p and (root/p.decode("utf8")).is_file()})
    excluded={"node_modules",".venv",".cache",".local",".release-work",".git","__pycache__","artifacts","runs"}
    return sorted(str(p.relative_to(root)).replace("\\","/") for p in root.rglob("*") if p.is_file() and not excluded.intersection(p.relative_to(root).parts) and not p.name.endswith(".local.json") and p.name!=".env")
def audit(root=ROOT):
    root=pathlib.Path(root).resolve();files=candidates(root);findings=[]
    patterns=[re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|sk-[A-Za-z0-9_-]{24,})"),re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")]
    secret=os.environ.get("PIPAPER_API_KEY","")
    for path in files:
        parts=pathlib.PurePosixPath(path).parts
        if any(p in parts for p in [".local",".release-work",".env","node_modules",".venv",".cache","runs","artifacts"]) or path.endswith(".local.json"):findings.append({"file":path,"reason":"private_path"});continue
        data=(root/path).read_bytes()
        if len(data)>90*1024*1024:findings.append({"file":path,"reason":"oversized_file"})
        try:text=data.decode("utf8")
        except UnicodeError:continue
        if any(p.search(text) for p in patterns) or secret and secret in text:findings.append({"file":path,"reason":"credential_pattern"})
        if re.search(r"[A-Za-z]:[\\/]Users[\\/]",text):findings.append({"file":path,"reason":"personal_absolute_path"})
    cfg=json.loads((root/"configs/model.example.json").read_bytes())
    if cfg["model"]["base_url"] or cfg["model"]["model_id"]:findings.append({"file":"configs/model.example.json","reason":"model_template_not_blank"})
    for path in ["configs/full-runtime-v4.json","configs/ac295-v6/C.json","agent/ac295-run-v6.ts"]:
        if path in files:findings.append({"file":path,"reason":"legacy_personal_runtime"})
    return {"status":"passed" if not findings else "failed","scanned_files":len(files),"findings":findings,"secret_values_printed":0}
if __name__=="__main__":
    argparse.ArgumentParser(description=__doc__).parse_args();v=audit();print(json.dumps(v,ensure_ascii=False,indent=2));raise SystemExit(0 if v["status"]=="passed" else 1)
