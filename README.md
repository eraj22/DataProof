# DataProof

DataProof is an experimental web app for auditable tabular question answering. It profiles an uploaded CSV/XLSX file, asks a Groq model for a structured analysis plan, executes only allowlisted operations, independently recomputes the result, and returns an answer, clarification, or abstention with a saved trajectory. This repository is an implementation work in progress, not a completed Phase 2 submission.

## Architecture

```text
CSV/XLSX + question -> profiler -> Groq JSON planner -> plan validator
                                              |                |
                                              | clarification  v
                                              |           pandas executor
                                              |                v
                                              +----------> verifier
                                                               v
                                                     answer / abstain
                                                               v
                                                       JSON trace in logs/
```

The planner receives column names, types, missing counts, and three example values per column. The uploaded full dataset stays local. Groq mode requires a configured API key. The local heuristic is a limited offline baseline and is not a substitute for Groq or DSBench.

## Install and run

Use Python 3.12. From the repository root:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:GROQ_API_KEY = "your-key-stored-locally"
python -m dataproof.web
```

Open `http://127.0.0.1:8000`. Do not commit `.env`, API keys, uploads, or private traces. Configure `GROQ_MODEL` to an available Groq model; default is `openai/gpt-oss-20b`, available on the account during the 2026-11-07 development check. Temperature is zero. API availability and model names should be checked before final runs. Local CSV/XLSX is limited to 20 MB upload, 100,000 rows, and 100 columns. The server binds to localhost by default and is meant for local development, not public deployment.

## Architecture and gap components

| Phase 1 gap | Component | Ablation switch | Intended metric |
|---|---|---|---|
| G1: task semantics may be missed despite execution success | JSON analysis contract and plan validation | `Config(contract=False)` changes the planner instruction; safety validation remains | semantic task accuracy and contract compliance |
| G2: claims lack execution evidence | independent recomputation and provenance fields | `Config(verifier=False)` | verifier precision/recall and unsafe acceptance |
| G3: ambiguous tasks need clarification or abstention | clarification and risk controller | `Config(abstention=False)` | unsafe-answer rate and appropriate abstention |

Current limitations: the verifier invokes the same deterministic operation implementation, so it does not yet provide independent algorithmic diversity. The system has no bounded repair turn. These limitations matter for the G2 claim and should be resolved and re-evaluated before submission.

## Reproduction

Deterministic tests:

```powershell
python -m unittest discover -s tests -v
```

Offline smoke pilot (synthetic data; nine fixed test tasks; three identical deterministic repeats):

```powershell
python experiments/run_eval.py --manifest data/pilot_manifest.json --mode E3_offline_pilot --split test --repeats 3 --output results/offline_pilot.json
```

Groq experiments can use the same manifest and `--mode E3`, `E5_no_contract`, `E5_no_verifier`, or `E5_no_abstention`. The script stores task-level status, correctness, latency, token count, tool calls, and traces. E1 uses `--mode E1`. Run development tasks first, freeze prompts and settings, then run the untouched test split. A proper DSBench task manifest and downloaded data are still required; the synthetic pilot is not comparable with the DSBench paper. The DSBench authors provide processed data separately: <https://github.com/LiqiangJing/DSBench/tree/main/data_analysis>. Respect their dataset rights notice.

After the five saved pilot runs, create the compact efficiency table with `python experiments/summarize.py`. It writes `results/pilot_summary.csv` from the task-level JSON files; it does not run the model again.

## Experiment status

| Required experiment | Status |
|---|---|
| E1 simpler baseline | Runner implemented; only synthetic offline smoke evaluation available |
| E2 base-paper approach | Not reproduced; DSBench environment/data and matching scoring required |
| E3 full system | Runnable with Groq key; no real Groq/DSBench evaluation saved |
| E4 gap-wise | Hypotheses and switches identified; labelled DSBench evaluation pending |
| E5 ablation | Switches and runner exist; meaningful final ablation pending |
| E6 efficiency and reliability | Per-task logging exists; final analysis pending |

The fixed synthetic test split contains nine tasks and is deliberately easy. Its measured results on 2026-11-07 are below. Each configuration ran three times; the accuracy standard deviation was 0.00 in each case. `openai/gpt-oss-20b` was used through Groq with temperature 0. The no-contract run was repeated after two rate-limit errors in its first attempt; the saved file contains only the paced rerun. These results are software pilot evidence, not evidence of DSBench performance or generalization.

| Pilot configuration | Correct per run | Mean accuracy | Total tokens / 27 runs | Mean task latency |
|---|---:|---:|---:|---:|
| E1 offline heuristic baseline | 6/9 | 0.667 | 0 | 2 ms |
| E3 full Groq system | 9/9 | 1.000 | 12,756 | 1,405 ms |
| E5 without contract instruction | 8/9 | 0.889 | 12,561 | 757 ms |
| E5 without verifier | 9/9 | 1.000 | 12,624 | 2,497 ms |
| E5 without abstention control | 6/9 | 0.667 | 12,709 | 1,939 ms |

The no-verifier score matching the full score means this pilot does not demonstrate a verifier benefit. All selected numeric questions were simple enough for the executor to solve; there were no natural wrong-output cases for it to catch. The three ambiguous questions drive the abstention difference. The pilot's easy task selection and repeated deterministic outputs are major validity limits.

## Gap-resolution table

| Gap | Method / component | Metric | Base paper result | Our result | Addressed? |
|---|---|---|---|---|---|
| G1 | Contract planner | semantic task accuracy | Not measured on selected tasks | Pending DSBench run | Not established |
| G2 | Verifier | false acceptance; precision/recall | Not reported in matching metric | Pending audited labels | Not established |
| G3 | Clarify/abstain | unsafe-answer rate; coverage | Not reported in matching metric | Pending ambiguous variants | Not established |

The DSBench paper reports aggregate data-analysis task success, but its aggregate number must not be placed into the gap table as if it were measured on our selected subset and metrics.

## Changes since Phase 1

The proposal anticipated a Python executor and separate verifier. This implementation uses a constrained JSON operation plan rather than executing model-generated Python, to make local execution safer and contract checks inspectable. The current tool supports common aggregations and simple filters. Phase 1 supervisor feedback was not supplied, so no claim is made that it was addressed. The base paper and three gaps have not been changed.

## Phase checklist and remaining requirements

Phase 1 literature review and proposal drafts are held outside this repository. Their source claims and the supervisor's approval/feedback require student review. A Phase 1 working baseline and initial results were not present in the GitHub repository when this work began.

For Phase 2, the pipeline, basic logging, three identifiable components, local web interface, dependency file, secret example, development log, and deterministic tests are present. The following remain open: full DSBench integration; fixed sufficiently large test split; three independent Groq runs per main configuration; E1-E6 on the same tasks and metrics; reproduced base-paper approach; gap-wise results, audited labels, ablation and failure frequencies; two representative successes and failures; measured improvement iteration; 8-10 page student-written IEEE/ACM paper with 25-30 verified references; Turnitin similarity and AI-writing reports; assigned project code/email; `phase2-final` release; and Classroom submission. Do not mark any of these complete until the saved evidence exists.

The course requires the student to write the paper in their own words. The evidence checklist is in `paper/authoring_checklist.md`. The source-code release and submission should be made only after the real results and final paper have been checked.
