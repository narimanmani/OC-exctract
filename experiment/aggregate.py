import csv,json
from pathlib import Path
rows=[]
for p in sorted(Path("pilot-results").rglob("run_status.json")):
    s=json.loads(p.read_text())
    rows.append(dict(repository=s["repository"],status=s.get("status","failed"),snapshots=len(s.get("snapshots",[])),failed_snapshots=len(s.get("failures",[])),history_verified=s.get("source_history_complete",False),validated_service_boundaries=False,full_experiment_complete=False))
out=Path("pilot-summary");out.mkdir(exist_ok=True)
with (out/"case_status.csv").open("w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]) if rows else ["repository","status"]);w.writeheader();w.writerows(rows)
(out/"status.json").write_text(json.dumps(dict(phase="fresh_extraction_pilot",case_reports=len(rows),full_experiment_complete=False,cases=rows),indent=2))
print(json.dumps(rows,indent=2))
