"""Run labelled evaluation manifest. Never calls a test result a benchmark reproduction."""
import argparse
import csv
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dataproof.core import Config, load_table, run

MODES = {"E1": Config(provider="heuristic", contract=False, verifier=False, abstention=False),
         "E3": Config(), "E3_offline_pilot": Config(provider="heuristic"),
         "E5_no_contract": Config(contract=False),
         "E5_no_verifier": Config(verifier=False), "E5_no_abstention": Config(abstention=False)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True, help="JSON list of id,split,file,question,expected,status")
    ap.add_argument("--mode", choices=list(MODES), required=True)
    ap.add_argument("--split", choices=["dev", "validation", "test"], default="test")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--request-delay", type=float, default=4.0, help="Seconds between Groq requests to respect token limits")
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    if args.repeats < 1:
        ap.error("repeats must be positive")
    manifest = Path(args.manifest).resolve()
    items = json.loads(manifest.read_text(encoding="utf-8"))
    selected = [x for x in items if x["split"] == args.split]
    if not selected:
        ap.error("no tasks for split")
    rows = []
    for repeat in range(args.repeats):
        for task in selected:
            frame = load_table(manifest.parent / task["file"])
            t0 = time.perf_counter()
            result = run(task["question"], frame, MODES[args.mode])
            correct = result["status"] == task["status"] and (task["status"] != "answered" or result["answer"] == task["expected"])
            rows.append({"id": task["id"], "split": args.split, "mode": args.mode, "repeat": repeat,
                         "status": result["status"], "correct": int(correct), "latency_ms": round((time.perf_counter()-t0)*1000, 2),
                         "tokens": result["usage"].get("total_tokens", 0), "tool_calls": sum(t["state"] == "execute" for t in result["trace"]),
                         "trace": result["trace"]})
            if MODES[args.mode].provider == "groq":
                time.sleep(args.request_delay)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"manifest": args.manifest, "mode": args.mode, "split": args.split, "rows": rows,
        "accuracy_mean": statistics.mean(statistics.mean(r["correct"] for r in rows if r["repeat"] == i) for i in range(args.repeats)),
        "accuracy_std": statistics.stdev([statistics.mean(r["correct"] for r in rows if r["repeat"] == i) for i in range(args.repeats)]) if args.repeats > 1 else None}, indent=2, default=str), encoding="utf-8")
    print(f"Saved {len(rows)} task runs to {output}")


if __name__ == "__main__":
    main()
