"""Restore 48 public papers from the pinned QASPER archive; never reads evaluation data."""
from __future__ import annotations
import argparse,hashlib,json,pathlib,tarfile,urllib.request
ROOT=pathlib.Path(__file__).resolve().parents[1]
URL="https://qasper-dataset.s3.us-west-2.amazonaws.com/qasper-train-dev-v0.3.tgz"
def sha(data):return hashlib.sha256(data).hexdigest()
def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf8")
def restore(root=ROOT,download=False,dataset="original47"):
    root=pathlib.Path(root).resolve();manifest=json.loads((root/"data/full-v1/manifests/corpus.json").read_bytes())
    archive=root/"data/raw/qasper-train-dev-v0.3.tgz"
    if not archive.resolve().is_relative_to(root):raise ValueError("Archive path escapes project")
    if not archive.exists():
        if not download:raise ValueError("Missing archive: use --download or place the pinned archive in data/raw/")
        archive.parent.mkdir(parents=True,exist_ok=True)
        with urllib.request.urlopen(URL,timeout=120) as src,archive.open("xb") as dst:
            while block:=src.read(1024*1024):dst.write(block)
    if sha(archive.read_bytes())!=manifest["source_archive_sha256"]:raise ValueError("Source archive hash differs")
    sources={};members=[]
    with tarfile.open(archive,"r:gz") as tar:
        for split,name in [("train","qasper-train-v0.3.json"),("validation","qasper-dev-v0.3.json")]:
            source=tar.extractfile(name)
            if source is None:raise ValueError("Archive member missing")
            data=source.read();sources[split]=json.loads(data)
            members.append({"source_split":split,"member":name,"sha256":sha(data),"papers":len(sources[split])})
    if members!=manifest["members"]:raise ValueError("Source member identity differs")
    papers=[]
    for entry in manifest["papers"]:
        matches=[]
        for split in sources.values():
            original=split.get(entry["paper_id"])
            if original:
                row={"paper_id":entry["paper_id"],**{k:original[k] for k in ("title","abstract","full_text")}}
                if sha(canonical(row))==entry["source_text_sha256"] and row["title"]==entry["title"]:matches.append(row)
        if not matches:raise ValueError("Pinned paper source differs")
        papers.append(matches[0])
    data=b"".join(canonical(p)+b"\n" for p in papers)
    if len(papers)!=manifest["paper_count"] or len({p["paper_id"] for p in papers})!=len(papers) or sha(data)!=manifest["files"]["papers.jsonl"]:raise ValueError("Restored corpus identity differs")
    if dataset=="agent295":
        extra=json.loads((root/"data/abc295-v3/manifests/corpus.json").read_bytes())
        patch_path=root/"data/abc295-v3/manifests/public-additions.jsonl"
        inventory=json.loads((root/"data/source-assets.json").read_bytes())
        if sha(patch_path.read_bytes())!=inventory["public_additions_sha256"]:raise ValueError("Public additions differ")
        patches={p["paper_id"]:p for p in map(json.loads,patch_path.read_text(encoding="utf8").splitlines())}
        if set(patches)!={p["paper_id"] for p in papers}:raise ValueError("Public additions scope differs")
        for paper in papers:
            patch=patches[paper["paper_id"]]
            if sha(canonical(paper))!=patch["base_paper_sha256"]:raise ValueError("Addition base paper differs")
            paper["full_text"].extend(patch["append_sections"]);paper.update(patch["metadata_updates"])
            if sha(canonical(paper))!=patch["final_paper_sha256"]:raise ValueError("Addition paper hash differs")
        data=b"".join(canonical(p)+b"\n" for p in papers)
        if sha(data)!=extra["files"]["papers.jsonl"]:raise ValueError("Restored agent295 corpus differs")
    elif dataset!="original47":raise ValueError("Unsupported dataset")
    target=root/("data/abc295-v3/corpus/papers.jsonl" if dataset=="agent295" else "data/full-v1/corpus/papers.jsonl")
    if not target.resolve().is_relative_to(root):raise ValueError("Corpus output escapes project")
    if target.exists() and target.read_bytes()!=data:raise ValueError("Existing corpus differs; preserve it before restoring")
    target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    return {"status":"verified","dataset":dataset,"papers":len(papers),"sha256":sha(data),"gold_loaded":False,"provider_calls":0}
if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--download",action="store_true");p.add_argument("--dataset",choices=["original47","agent295"],default="original47");a=p.parse_args()
    print(json.dumps(restore(download=a.download,dataset=a.dataset)))
