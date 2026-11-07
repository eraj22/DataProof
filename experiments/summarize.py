"""Build a compact, reproducible pilot table from saved task-level results."""
import csv
import json
import statistics
from pathlib import Path


def main():
    result_dir = Path("results")
    files = ["baseline_pilot.json", "groq_pilot.json", "no_contract_pilot.json",
             "no_verifier_pilot.json", "no_abstention_pilot.json"]
    summary = []
    for name in files:
        data = json.loads((result_dir / name).read_text(encoding="utf-8"))
        rows = data["rows"]
        summary.append({"file": name, "mode": data["mode"], "tasks": len({r["id"] for r in rows}),
            "repeats": len({r["repeat"] for r in rows}), "accuracy_mean": data["accuracy_mean"],
            "accuracy_std": data["accuracy_std"], "latency_ms_mean": round(statistics.mean(r["latency_ms"] for r in rows), 2),
            "tokens_total": sum(r["tokens"] for r in rows), "tool_calls_total": sum(r["tool_calls"] for r in rows),
            "errors": sum(r["status"] == "error" for r in rows),
            "clarifications": sum(r["status"] == "clarify" for r in rows)})
    with (result_dir / "pilot_summary.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=summary[0].keys())
        writer.writeheader()
        writer.writerows(summary)


if __name__ == "__main__":
    main()
