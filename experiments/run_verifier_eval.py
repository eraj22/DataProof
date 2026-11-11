"""Evaluate verifier sensitivity with clean and deterministically corrupted outputs."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dataproof.core import execute_plan, load_table, verify


def corrupt(value):
    if isinstance(value, bool):
        return not value
    if isinstance(value, (int, float)):
        return value + 1
    if isinstance(value, list):
        return value[:-1] if value else [{"value": 1}]
    return "corrupted"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--split", default="test")
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    manifest = Path(args.manifest).resolve()
    tasks = json.loads(manifest.read_text(encoding="utf-8"))
    rows = []
    for task in tasks:
        if task["split"] != args.split or task.get("oracle_plan") is None:
            continue
        frame = load_table(manifest.parent / task["file"])
        good = execute_plan(task["oracle_plan"], frame)
        bad = dict(good)
        bad["value"] = corrupt(good["value"])
        good_verdict = verify(task["oracle_plan"], frame, good)["passed"]
        bad_verdict = verify(task["oracle_plan"], frame, bad)["passed"]
        rows.append({"id":task["id"],"clean_accepted":good_verdict,"corruption_rejected":not bad_verdict})
    summary = {"tasks":len(rows),"clean_acceptance":sum(r["clean_accepted"] for r in rows)/len(rows),
               "corruption_recall":sum(r["corruption_rejected"] for r in rows)/len(rows),"rows":rows}
    out=Path(args.output); out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in summary.items() if k!='rows'}))


if __name__ == "__main__":
    main()
