"""Fresh measurement pilot; detected components are NOT validated services."""
from __future__ import annotations
import argparse, gzip, hashlib, json, subprocess, sys, time, traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import organizationalCoupling as oc

ROOT=Path.cwd()
UTC=timezone.utc
def run(argv,cwd=None,timeout=1800):
    p=subprocess.run(argv,cwd=cwd,text=True,capture_output=True,timeout=timeout)
    if p.returncode: raise RuntimeError(repr(argv[:5])+"\n"+p.stderr[-2500:])
    return p.stdout
def save(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,indent=2,allow_nan=False),encoding="utf-8")
def dt(s):return datetime.fromisoformat(s.replace("Z","+00:00")).astimezone(UTC)
def fixtures():
    dates=["2026-10-26T00:00:00Z","2026-10-26T12:00:00Z","2026-10-27T12:00:00Z","2026-10-31T12:00:00Z","2026-11-01T00:00:00Z","2026-11-01T12:00:00Z"]
    d=pd.DataFrame([dict(project="toy",commit_sha=str(i),author_date=x,author_email="dev@example",service="a" if i%2 else "b",additions=1,deletions=0) for i,x in enumerate(dates)])
    old=oc._prepare_coupling_dataframe(d,project="toy",start=pd.Timestamp("2026-10-26",tz="UTC"),end=pd.Timestamp("2026-11-01",tz="UTC"),start_inclusive=False,end_inclusive=True)
    assert len(old)==4
    assert oc.compute_oc_from_heatmap(pd.DataFrame([[0.,4.],[4.,0.]]))==8.
    assert oc._extract_author_identifier("dev@a.example")==oc._extract_author_identifier("dev@b.example")
    correct=oc._prepare_coupling_dataframe(d,project="toy",start=pd.Timestamp("2026-10-26",tz="UTC"),end=pd.Timestamp("2026-11-02",tz="UTC"),start_inclusive=True,end_inclusive=False)
    assert len(correct)==6
    return dict(status="pass",legacy_window_rows=4,half_open_rows=6,legacy_symmetric_scalar=8.,upper_triangle_mean=4.,identity_collision_reproduced=True)
def commits(repo,freeze,anchors,output):
    lines=run(["git","log",freeze,"--format=%H%x09%aI%x09%cI%x09%aE"],repo).splitlines()
    selected=[]
    for line in lines:
        p=line.split("\t",3)
        if len(p)==4 and any(a-timedelta(weeks=8)<=dt(p[1])<a for a in anchors):
            selected.append(p)
    rows=[]
    for index,(sha,ad,cd,email) in enumerate(selected):
        parents=run(["git","rev-list","--parents","-n","1",sha],repo).strip().split()
        command=["git","diff","--numstat","--no-renames",parents[1],sha] if len(parents)>1 else ["git","show","--format=","--numstat","--no-renames",sha]
        identity=hashlib.sha256(email.strip().casefold().encode()).hexdigest()
        for line in run(command,repo).splitlines():
            p=line.split("\t",2)
            if len(p)!=3:continue
            a,d,name=p
            rows.append(dict(commit_sha=sha,author_date=ad,committer_date=cd,author_id=identity,filename=name,additions=int(a) if a.isdigit() else 0,deletions=int(d) if d.isdigit() else 0,binary_or_unknown=not(a.isdigit() and d.isdigit()),is_merge=len(parents)>2))
        if index%250==0:print("Commit details",index,"/",len(selected),flush=True)
    d=pd.DataFrame(rows,columns=["commit_sha","author_date","committer_date","author_id","filename","additions","deletions","binary_or_unknown","is_merge"])
    d.to_csv(output,index=False,compression="gzip")
    return d,len(selected)
def prefix(p):return str(p).replace("\\","/").strip("/")
def assign(name,mapping):
    for p,s in mapping:
        if p and (name==p or name.startswith(p+"/")):return s
    return next((s for p,s in mapping if not p),None)
def compute_oc(raw,repository,components,anchor,out):
    mapping=sorted([(prefix(c["path"]),prefix(c["path"]) or "__root__") for c in components],key=lambda x:(-len(x[0]),x[0]))
    population=sorted(set(x[1] for x in mapping))
    d=raw.copy();d["project"]=repository;d["author_email"]=d["author_id"]
    d["service"]=[assign(x,mapping) for x in d.filename]
    d["service_map_validated"]=False
    d.to_csv(out/"commit_component_mapping.csv.gz",index=False,compression="gzip")
    results=[]
    for k in range(8):
        start=anchor-timedelta(weeks=8-k);end=start+timedelta(weeks=1)
        g=oc._prepare_coupling_dataframe(d,project=repository,start=pd.Timestamp(start),end=pd.Timestamp(end),start_inclusive=True,end_inclusive=False)
        active=sorted(g.service.unique()) if not g.empty else []
        h=pd.DataFrame(0.,index=population,columns=population)
        for i,a in enumerate(active):
            for b in active[i+1:]:
                v=oc._compute_service_coupling(g,a,b);h.loc[a,b]=v;h.loc[b,a]=v
        pairs=len(population)*(len(population)-1)//2
        results.append(dict(week_start=start.isoformat(),week_end_exclusive=end.isoformat(),candidate_components=len(population),active_components=len(active),oc_upstream_symmetric_aggregation=oc.compute_oc_from_heatmap(h),oc_distinct_pair_mean=float(np.triu(h.to_numpy(),1).sum())/pairs if pairs else None,oc_applicable=len(active)>=2,boundary_map_validated=False,identity_rule="sha256_mailmap_full_email",time_basis="author_date_for_comparator",interpretation="raw_measurement_pilot"))
        h.to_csv(out/("heatmap_"+start.strftime("%Y-%m-%d")+".csv.gz"),compression="gzip")
    pd.DataFrame(results).to_csv(out/"oc_weekly_summary.csv",index=False)
    return results
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--system",required=True);args=ap.parse_args()
    manifest=json.loads(Path("experiment/manifest.json").read_text())
    case=next(x for x in manifest["systems"] if x["repository"]==args.system)
    out=ROOT/"artifacts"/args.system.replace("/","_");out.mkdir(parents=True,exist_ok=True)
    status=dict(repository=args.system,phase="fresh_extraction_pilot",status="started",full_experiment_complete=False,source_history_complete=False,service_boundaries_validated=False,snapshots=[],failures=[],cimet_base_sha=manifest["cimet_base_sha"],oc_base_sha=manifest["oc_base_sha"])
    save(out/"run_status.json",status)
    save(out/"oc_fixtures.json",fixtures())
    jar=(ROOT/"toolkit"/"cimet-1.0-SNAPSHOT-jar-with-dependencies.jar").resolve()
    status["jar_sha256"]=hashlib.sha256(jar.read_bytes()).hexdigest()
    work=ROOT/"case-work";(work/"clone").mkdir(parents=True,exist_ok=True)
    repo=work/"clone"/args.system.split("/")[-1]
    if not repo.exists():
        print("Cloning",args.system,flush=True)
        run(["git","clone","--no-checkout","--single-branch","--branch",case["branch"],"https://github.com/"+args.system+".git",str(repo)],timeout=2400)
    freeze=case["freeze_candidate_sha"]
    run(["git","cat-file","-e",freeze+"^{commit}"],repo)
    run(["git","merge-base","--is-ancestor",freeze,"origin/"+case["branch"]],repo)
    status["source_history_complete"]=True;status["freeze_sha"]=freeze
    save(out/"run_status.json",status)
    anchors=[dt(x) for x in manifest["pilot_anchors"]+manifest.get("active_era_extra_anchors",{}).get(args.system,[])]
    raw,n=commits(repo,freeze,anchors,out/"raw_commit_files.csv.gz")
    status["commits_in_pilot_lookbacks"]=n
    for anchor in anchors:
        key=anchor.strftime("%Y-%m-%d");folder=out/key;folder.mkdir(exist_ok=True)
        sha=run(["git","rev-list","--first-parent","-1","--before="+(anchor-timedelta(seconds=1)).isoformat(),freeze],repo).strip()
        if not sha:
            status["failures"].append(dict(anchor=key,error="no_reachable_snapshot"));continue
        config=work/("config-"+key+".json")
        save(config,dict(systemName=args.system.replace("/","_"),repositoryURL="https://github.com/"+args.system+".git",branch=case["branch"]))
        target=folder/"snapshot";start=time.monotonic()
        try:
            p=subprocess.run(["java","-Xmx6g","-cp",str(jar),"study.FreshStudyRunner",str(config),sha,str(target)],cwd=work,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=1200)
            (folder/"cimet.log").write_text(p.stdout,encoding="utf-8")
            if p.returncode:raise RuntimeError("CIMET exit "+str(p.returncode))
            metrics=json.loads(Path(str(target)+".metrics.json").read_text())
            ir=Path(str(target)+".ir.json")
            if ir.exists():
                with gzip.open(str(ir)+".gz","wb") as f:f.write(ir.read_bytes())
                ir.unlink()
            components=metrics["components"]
            tracked=run(["git","ls-tree","-r","--name-only",sha],repo).splitlines()
            deploy=[x for x in tracked if "dockerfile" in Path(x).name.casefold() or "docker-compose" in Path(x).name.casefold() or x.endswith(("Chart.yaml","deployment.yaml"))]
            save(folder/"deployment_evidence_candidates.json",dict(files=deploy,validated=False))
            weekly=compute_oc(raw,args.system,components,anchor,folder)
            status["snapshots"].append(dict(anchor=key,sha=sha,elapsed_seconds=round(time.monotonic()-start,2),candidate_components=len(components),components_with_2plus_operations=sum(c["operations"]>=2 for c in components),http_endpoints=sum(c["http_endpoints"] for c in components),oc_weeks=len(weekly),architecture_scope_validated=False))
            print(args.system,key,status["snapshots"][-1],flush=True)
        except Exception as ex:
            status["failures"].append(dict(anchor=key,sha=sha,error=str(ex),elapsed_seconds=round(time.monotonic()-start,2)))
            print("Snapshot failed",args.system,key,type(ex).__name__,str(ex)[:200],flush=True)
        save(out/"run_status.json",status)
    status["status"]="pilot_complete" if not status["failures"] else "pilot_partial"
    status["remaining_before_primary_experiment"]=["validate_deployable_service_lineage","audit_framework_endpoint_coverage","full_weekly_extraction","validate_PTC_comparator","locked_model_evaluation","independent_architectural_review"]
    save(out/"run_status.json",status)
    save(out/"SHA256SUMS.json",{str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob("*") if p.is_file() and p.name!="SHA256SUMS.json"})
if __name__=="__main__":main()
