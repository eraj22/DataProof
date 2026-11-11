"""Build a fixed, contract-compatible benchmark from official DSBench workbooks.

The generated CSV files are local derivatives and are intentionally ignored by git.
The manifest records the DSBench competition ID, workbook, sheet and detected header.
"""
import argparse
import json
import math
from pathlib import Path

import pandas as pd


def clean_name(value, index):
    text = str(value).strip() if pd.notna(value) else ""
    return text[:60] if text and text.lower() != "nan" else f"column_{index+1}"


def detect_table(raw):
    best = None
    limit = min(len(raw) - 6, 80)
    for row in range(max(0, limit)):
        values = raw.iloc[row]
        present = [i for i, v in enumerate(values) if pd.notna(v) and str(v).strip()]
        if len(present) < 3:
            continue
        lo, hi = min(present), max(present)
        if hi - lo + 1 > 25:
            continue
        headers = [clean_name(raw.iat[row, c], c) for c in range(lo, hi + 1)]
        if len(set(headers)) != len(headers):
            continue
        body = raw.iloc[row + 1:, lo:hi + 1].copy()
        body.columns = headers
        body = body.dropna(how="all")
        if len(body) < 20:
            continue
        numeric = []
        for col in body.columns:
            converted = pd.to_numeric(body[col], errors="coerce")
            if converted.notna().mean() >= 0.8 and converted.notna().sum() >= 20:
                body[col] = converted
                numeric.append(col)
        if len(numeric) < 2:
            continue
        body = body.iloc[:5000].reset_index(drop=True)
        score = len(body) * min(len(numeric), 4)
        candidate = (score, row, body, numeric)
        if best is None or score > best[0]:
            best = candidate
    return best


def exact(value):
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsbench-root", required=True, help="Extracted DSBench data directory containing competition folders")
    ap.add_argument("--output", default="data/dsbench_derived")
    ap.add_argument("--tables", type=int, default=7)
    args = ap.parse_args()
    root = Path(args.dsbench_root).resolve()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    candidates = []
    for book in sorted(root.glob("*/*.xlsx")):
        competition = book.parent.name
        try:
            excel = pd.ExcelFile(book)
            for sheet in excel.sheet_names:
                if sheet.lower() == "formats":
                    continue
                raw = pd.read_excel(book, sheet_name=sheet, header=None)
                found = detect_table(raw)
                if found:
                    score, header, frame, numeric = found
                    candidates.append((score, competition, book, sheet, header, frame, numeric))
        except Exception:
            continue
    # One table per competition prevents a single workbook dominating the split.
    selected = []
    used = set()
    for item in sorted(candidates, key=lambda x: (-x[0], x[1], x[3])):
        if item[1] not in used:
            selected.append(item)
            used.add(item[1])
        if len(selected) == args.tables:
            break
    if len(selected) < args.tables:
        selected_keys = {(x[1], x[2].name, x[3]) for x in selected}
        for item in sorted(candidates, key=lambda x: (-x[0], x[1], x[3])):
            key = (item[1], item[2].name, item[3])
            if key not in selected_keys:
                selected.append(item)
                selected_keys.add(key)
            if len(selected) == args.tables:
                break
    if len(selected) < args.tables:
        raise SystemExit(f"Only {len(selected)} suitable DSBench tables detected")

    tasks = []
    provenance = []
    for table_index, (_, competition, book, sheet, header, frame, numeric) in enumerate(selected):
        filename = f"table_{table_index+1:02d}.csv"
        frame.to_csv(out / filename, index=False)
        a, b = numeric[:2]
        threshold = exact(frame[b].dropna().median())
        filtered = frame[frame[b] > threshold]
        specs = [
            (f"What is the average {a}?", exact(frame[a].mean()), "answered", "mean", {"operation":"mean","column":a,"filters":[],"group_by":[]}),
            (f"What is the total {a}?", exact(frame[a].sum()), "answered", "sum", {"operation":"sum","column":a,"filters":[],"group_by":[]}),
            (f"What is the maximum {b}?", exact(frame[b].max()), "answered", "max", {"operation":"max","column":b,"filters":[],"group_by":[]}),
            (f"What is the minimum {b}?", exact(frame[b].min()), "answered", "min", {"operation":"min","column":b,"filters":[],"group_by":[]}),
            (f"What is the median {a}?", exact(frame[a].median()), "answered", "median", {"operation":"median","column":a,"filters":[],"group_by":[]}),
            ("How many rows are there?", len(frame), "answered", "count", {"operation":"count","column":None,"filters":[],"group_by":[]}),
            (f"What is the total {a} where {b} is greater than {threshold}?", exact(filtered[a].sum()), "answered", "filtered_sum", {"operation":"sum","column":a,"filters":[{"column":b,"op":"gt","value":threshold}],"group_by":[]}),
            ("What is the average value?", None, "clarify", "ambiguous_metric", None),
            ("What changed in this dataset?", None, "clarify", "missing_comparison", None),
        ]
        for task_index, (question, expected, status, category, oracle_plan) in enumerate(specs):
            ordinal = table_index * len(specs) + task_index
            split = "dev" if table_index == 0 else ("validation" if table_index in {1, 6} else "test")
            tasks.append({"id": f"dsd{ordinal+1:03d}", "split": split,
                          "file": filename, "question": question, "expected": expected,
                          "status": status, "category": category, "oracle_plan": oracle_plan,
                          "source_competition": competition})
        provenance.append({"file": filename, "competition_id": competition, "workbook": book.name,
                           "sheet": sheet, "header_row_zero_based": header, "rows": len(frame),
                           "columns": list(frame.columns), "numeric_columns_used": [a, b]})
    (out / "manifest.json").write_text(json.dumps(tasks, indent=2), encoding="utf-8")
    (out / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    counts = {name:sum(t["split"] == name for t in tasks) for name in ("dev","validation","test")}
    print(f"Built {len(tasks)} tasks from {len(selected)} DSBench tables: {counts}")


if __name__ == "__main__":
    main()
