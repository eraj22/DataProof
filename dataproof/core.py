"""Constrained agent pipeline. LLMs propose JSON; Python owns all data operations."""
import csv
import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


OPS = {"count", "sum", "mean", "min", "max", "median", "nunique"}
FILTER_OPS = {"eq", "ne", "gt", "ge", "lt", "le"}


class AnalysisError(ValueError):
    pass


def load_table(path):
    path = Path(path)
    if path.suffix.lower() == ".csv":
        frame = pd.read_csv(path)
    elif path.suffix.lower() in {".xlsx", ".xlsm"}:
        frame = pd.read_excel(path)
    else:
        raise AnalysisError("Upload a CSV or XLSX file.")
    if frame.empty or len(frame.columns) > 100 or len(frame) > 100_000:
        raise AnalysisError("Dataset must have 1-100,000 rows and at most 100 columns.")
    if len(set(map(str, frame.columns))) != len(frame.columns):
        raise AnalysisError("Duplicate column names are unsupported.")
    frame.columns = [str(c) for c in frame.columns]
    return frame


def profile(frame):
    return {"rows": len(frame), "columns": [{"name": c, "dtype": str(frame[c].dtype),
            "missing": int(frame[c].isna().sum()), "examples": [str(v)[:60] for v in frame[c].dropna().unique()[:3]]}
            for c in frame.columns]}


def validate_plan(plan, frame):
    if not isinstance(plan, dict):
        raise AnalysisError("Plan must be a JSON object.")
    allowed = {"operation", "column", "filters", "group_by", "assumptions", "clarification"}
    if set(plan) - allowed:
        raise AnalysisError("Unknown plan fields.")
    if plan.get("clarification"):
        return plan
    op = plan.get("operation")
    col = plan.get("column")
    if op not in OPS or (op != "count" and col not in frame.columns):
        raise AnalysisError("Unknown operation or metric column.")
    if op == "count" and col is not None and col not in frame.columns:
        raise AnalysisError("Unknown count column.")
    groups = plan.get("group_by", [])
    if not isinstance(groups, list) or len(groups) > 2 or any(c not in frame.columns for c in groups):
        raise AnalysisError("Invalid grouping.")
    filters = plan.get("filters", [])
    if not isinstance(filters, list) or len(filters) > 4:
        raise AnalysisError("Invalid filters.")
    for f in filters:
        if not isinstance(f, dict) or set(f) != {"column", "op", "value"} or f["column"] not in frame.columns or f["op"] not in FILTER_OPS:
            raise AnalysisError("Invalid filter.")
    return plan


def execute_plan(plan, frame):
    validate_plan(plan, frame)
    if plan.get("clarification"):
        raise AnalysisError("A clarification is required.")
    selected = frame.copy()
    for f in plan.get("filters", []):
        series = selected[f["column"]]
        value = f["value"]
        if pd.api.types.is_numeric_dtype(series):
            try:
                value = float(value)
            except (ValueError, TypeError):
                raise AnalysisError("Numeric filter has a nonnumeric value.")
        else:
            series = series.astype(str)
            value = str(value)
        predicates = {"eq": lambda: series == value, "ne": lambda: series != value,
                      "gt": lambda: series > value, "ge": lambda: series >= value,
                      "lt": lambda: series < value, "le": lambda: series <= value}
        selected = selected[predicates[f["op"]]()]
    groups = plan.get("group_by", [])
    op, col = plan["operation"], plan.get("column")
    if groups:
        grouped = selected.groupby(groups, dropna=False)
        result = grouped.size() if op == "count" and col is None else getattr(grouped[col], op)()
        output = result.reset_index(name="value").to_dict(orient="records")
    else:
        output = len(selected) if op == "count" and col is None else getattr(selected[col], op)()
        if hasattr(output, "item"):
            output = output.item()
    return {"value": output, "rows_used": len(selected), "input_rows": len(frame)}


def verify(plan, frame, output):
    """Independent recomputation and basic provenance checks."""
    try:
        validate_plan(plan, frame)
        expected = execute_plan(plan, frame)
        passed = expected["value"] == output.get("value") and expected["rows_used"] == output.get("rows_used")
        return {"passed": bool(passed), "checks": {"plan_valid": True, "recomputed_value": bool(passed),
                "rows_used": expected["rows_used"], "source_columns": sorted(set(([plan.get("column")] if plan.get("column") else []) +
                plan.get("group_by", []) + [f["column"] for f in plan.get("filters", [])]))}}
    except (AnalysisError, KeyError, TypeError, ValueError) as exc:
        return {"passed": False, "checks": {"plan_valid": False}, "reason": str(exc)}


def groq_json(messages, model=None):
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise AnalysisError("Set GROQ_API_KEY in the local environment.")
    body = json.dumps({"model": model or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
                       "messages": messages, "temperature": 0, "response_format": {"type": "json_object"}}).encode()
    req = urllib.request.Request("https://api.groq.com/openai/v1/chat/completions", body,
            {"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=45) as res:
                data = json.load(res)
            return json.loads(data["choices"][0]["message"]["content"]), data.get("usage", {})
        except urllib.error.HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt == 2:
                raise AnalysisError("Groq HTTP error " + str(exc.code)) from exc
            time.sleep(2 ** attempt)
        except (urllib.error.URLError, KeyError, json.JSONDecodeError) as exc:
            raise AnalysisError("Groq request failed: " + str(exc)) from exc


SYSTEM = """You are a careful data analyst. Return only a JSON object with keys operation, column, filters, group_by, assumptions, clarification. Operations: count,sum,mean,min,max,median,nunique. Filters are objects with column,op,value; op is eq,ne,gt,ge,lt,le. Use exact column names. If the user's metric, time range, grouping, or filter is materially ambiguous, set clarification to a concise question and do not guess. Never invent columns. No Python code."""


def heuristic_plan(question, frame):
    """Offline development baseline, deliberately limited and never labelled Groq."""
    q = question.lower()
    matches = [c for c in frame.columns if re.search(r"\b" + re.escape(c.lower()) + r"\b", q)]
    op = next((name for name, terms in {"mean": ["average", "mean"], "sum": ["total", "sum"],
          "min": ["minimum", "lowest"], "max": ["maximum", "highest"], "median": ["median"],
          "count": ["count", "how many"], "nunique": ["unique", "distinct"]}.items()
          if any(t in q for t in terms)), None)
    if not op or (op != "count" and len(matches) != 1):
        return {"clarification": "Which exact metric and column should I use?"}
    return {"operation": op, "column": matches[0] if matches else None,
            "filters": [], "group_by": [], "assumptions": []}


@dataclass
class Config:
    contract: bool = True
    verifier: bool = True
    abstention: bool = True
    provider: str = "groq"


def run(question, frame, config=None):
    config = config or Config()
    trace = []
    started = time.perf_counter()
    usage = {}
    def event(state, **fields):
        trace.append({"state": state, "elapsed_ms": round((time.perf_counter()-started)*1000, 2), **fields})
    card = profile(frame)
    event("profile", rows=card["rows"], columns=[c["name"] for c in card["columns"]])
    try:
        if config.provider == "heuristic":
            plan = heuristic_plan(question, frame)
        elif config.provider == "groq":
            plan, usage = groq_json([{"role": "system", "content": SYSTEM if config.contract else SYSTEM.replace("If the user's metric, time range, grouping, or filter is materially ambiguous, set clarification to a concise question and do not guess.", "")},
                {"role": "user", "content": json.dumps({"question": question, "data_profile": card})}])
        else:
            raise AnalysisError("Unknown provider.")
        event("plan", plan=plan, provider=config.provider)
        if plan.get("clarification"):
            if config.abstention:
                event("clarify", question=plan["clarification"])
                return {"status": "clarify", "answer": plan["clarification"], "trace": trace, "usage": usage}
            raise AnalysisError("Planner did not produce a complete plan.")
        validate_plan(plan, frame)
        event("contract", valid=True, enabled=config.contract)
        output = execute_plan(plan, frame)
        event("execute", output=output)
        verdict = verify(plan, frame, output) if config.verifier else {"passed": True, "checks": {"disabled": True}}
        event("verify", verdict=verdict)
        if not verdict["passed"]:
            raise AnalysisError("Independent verification failed.")
        event("answer", value=output["value"])
        return {"status": "answered", "answer": output["value"], "evidence": verdict,
                "plan": plan, "rows_used": output["rows_used"], "trace": trace, "usage": usage}
    except (AnalysisError, KeyError, TypeError, ValueError) as exc:
        state = "abstain" if config.abstention else "error"
        event(state, reason=str(exc))
        return {"status": "abstained" if config.abstention else "error", "answer": str(exc), "trace": trace, "usage": usage}
