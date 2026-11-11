"""Create Phase 2 tables and representative cases from saved experiment JSON."""
import csv
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(name):
    return json.loads((ROOT / "results" / name).read_text(encoding="utf-8"))


def main():
    manifest = {x["id"]: x for x in json.loads((ROOT / "data/dsbench_derived/manifest.json").read_text(encoding="utf-8"))}
    configurations = [
        ("E1 heuristic baseline", "E1_dsbench_derived.json"),
        ("E3 DataProof", "E3_dsbench_derived.json"),
        ("Pilot no contract", "no_contract_pilot.json"),
        ("Pilot no verifier", "no_verifier_pilot.json"),
        ("Pilot no abstention", "no_abstention_pilot.json"),
    ]
    summary = []
    for label, filename in configurations:
        data = read(filename)
        rows = data["rows"]
        per_repeat = [statistics.mean(x["correct"] for x in rows if x["repeat"] == repeat)
                      for repeat in sorted({x["repeat"] for x in rows})]
        summary.append({"configuration": label, "result_file": filename,
            "unique_tasks": len({x["id"] for x in rows}), "repeats": len(per_repeat),
            "accuracy_mean": statistics.mean(per_repeat),
            "accuracy_std": statistics.stdev(per_repeat) if len(per_repeat)>1 else 0,
            "latency_ms_mean": statistics.mean(x["latency_ms"] for x in rows),
            "tokens_total": sum(x["tokens"] for x in rows),
            "tool_calls_total": sum(x["tool_calls"] for x in rows),
            "error_statuses": sum(x["status"] == "error" for x in rows),
            "provider_errors": sum(x["status"] == "error" and x["trace"] and
                str(x["trace"][-1].get("reason","")).startswith("Groq") for x in rows)})
    with (ROOT / "results/phase2_summary.csv").open("w",newline="",encoding="utf-8") as stream:
        writer=csv.DictWriter(stream,fieldnames=summary[0].keys()); writer.writeheader(); writer.writerows(summary)

    full = read("E3_dsbench_derived.json")["rows"]
    by_category = defaultdict(list)
    failures = []
    successes = []
    for row in full:
        task = manifest[row["id"]]
        by_category[task["category"]].append(row["correct"])
        enriched = {"task": task, "repeat": row["repeat"], "status": row["status"],
                    "correct": bool(row["correct"]), "latency_ms": row["latency_ms"], "trace": row["trace"]}
        (successes if row["correct"] else failures).append(enriched)
    categories = [{"category":k,"runs":len(v),"accuracy":statistics.mean(v)} for k,v in sorted(by_category.items())]
    with (ROOT / "results/category_accuracy.csv").open("w",newline="",encoding="utf-8") as stream:
        writer=csv.DictWriter(stream,fieldnames=categories[0].keys()); writer.writeheader(); writer.writerows(categories)

    failure_types=Counter()
    for item in failures:
        expected=item["task"]["status"]; actual=item["status"]
        if expected == "answered" and actual == "clarify": reason="over_clarification"
        elif expected == "answered" and actual == "answered": reason="wrong_execution_semantics"
        elif actual == "error": reason="service_or_schema_error"
        else: reason="decision_error"
        item["failure_category"]=reason; failure_types[reason]+=1
    case_file={"failure_frequency_by_run":dict(failure_types),
               "representative_successes":successes[:2],"representative_failures":failures[:2],
               "all_failures":failures}
    (ROOT / "results/failure_analysis.json").write_text(json.dumps(case_file,indent=2,default=str),encoding="utf-8")

    verifier=read("E4_verifier_fault_injection.json")
    evidence={"evaluation_scope":{"source":"DSBench official workbooks","derived_tasks":54,
              "note":"Contract-compatible questions derived from workbook tables; not official DSBench questions."},
              "E1":summary[0],"E2":{"source":"DSBench paper","reported_data_analysis_success":0.3412,
              "reproduced":False,"comparability":"Published aggregate is contextual only; task definitions differ."},
              "E3":summary[1],"E4":{"verifier_fault_injection":{k:v for k,v in verifier.items() if k!='rows'},
              "ambiguity_accuracy":next(x["accuracy"] for x in categories if x["category"]=="ambiguous_metric")},
              "E5":{"pilot_no_contract":summary[2],"pilot_no_verifier":summary[3],"pilot_no_abstention":summary[4],
              "limitation":"Ablations use the nine-task pilot and are directional, not final DSBench-derived estimates."},
              "E6":{"latency_ms_mean":summary[1]["latency_ms_mean"],"tokens_total":summary[1]["tokens_total"],
              "tool_calls_total":summary[1]["tool_calls_total"],"provider_errors":summary[1]["provider_errors"]},
              "failures":{"total_failed_runs":len(failures),"categories":dict(failure_types)}}
    (ROOT / "results/phase2_evidence.json").write_text(json.dumps(evidence,indent=2),encoding="utf-8")
    (ROOT / "logs").mkdir(exist_ok=True)
    (ROOT / "logs/representative_cases.json").write_text(json.dumps({
        "successes":successes[:2],"failures":failures[:2]},indent=2,default=str),encoding="utf-8")
    print(json.dumps(evidence,indent=2))


if __name__ == "__main__":
    main()
