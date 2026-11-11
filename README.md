# DataProof

DataProof is a research prototype for auditable tabular question answering. It profiles an uploaded CSV/XLSX file, asks a Groq model for a structured analysis plan, executes only allowlisted operations, independently recomputes the result, and returns an answer, clarification, or abstention with a saved trajectory.

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

Build the fixed DSBench-derived data from an extracted copy of the processed DSBench workbooks:

```powershell
python data/build_dsbench_derived.py --dsbench-root C:\path\to\dsbench_extracted\data --output data\dsbench_derived --tables 7
```

The builder produces 63 tasks from seven workbook tables: 9 development, 18 validation and 36 reserved final tasks. CSV derivatives are ignored by git because DSBench states that its code license does not cover external datasets. The manifest and provenance files are committed. The completed main evaluation predates the later split refinement and contains 54 tasks, three repeats and 162 calls; this is stated explicitly in the evidence pack.

Offline smoke pilot (synthetic data; nine fixed test tasks; three identical deterministic repeats):

```powershell
python experiments/run_eval.py --manifest data/pilot_manifest.json --mode E3_offline_pilot --split test --repeats 3 --output results/offline_pilot.json
```

Groq experiments can use the same manifest and `--mode E3`, `E5_no_contract`, `E5_no_verifier`, or `E5_no_abstention`. The script stores task-level status, correctness, latency, token count, tool calls, and traces. E1 uses `--mode E1`. Run development tasks first, freeze prompts and settings, then run the untouched test split. A proper DSBench task manifest and downloaded data are still required; the synthetic pilot is not comparable with the DSBench paper. The DSBench authors provide processed data separately: <https://github.com/LiqiangJing/DSBench/tree/main/data_analysis>. Respect their dataset rights notice.

After the five saved pilot runs, create the compact efficiency table with `python experiments/summarize.py`. It writes `results/pilot_summary.csv` from the task-level JSON files; it does not run the model again.

`experiments/run_phase2.ps1` documents the complete final-run sequence. `experiments/analyze_phase2.py` regenerates the summary, category accuracy, failure taxonomy, representative cases and evidence ledger from saved JSON.

## Experiment status

| Required experiment | Status |
|---|---|
| E1 simpler baseline | Complete: 54 DSBench-derived tasks × 3 repeats; 62.96% mean accuracy |
| E2 base-paper approach | Published DSBench result recorded as 34.12%; not reproduced and not directly comparable because task definitions differ |
| E3 full system | Complete: 54 derived tasks × 3 repeats; 95.68% mean accuracy, 1.07 percentage-point SD |
| E4 gap-wise | Contract comparison, 28-task verifier fault injection, and ambiguity categories saved |
| E5 ablation | Contract, verifier and abstention switches evaluated on the nine-task pilot; directional limitation stated |
| E6 efficiency and reliability | Complete for E3: 2,375 ms mean latency, 146,402 total tokens, 122 tool calls, zero provider errors |

### Main evaluation and failure analysis

The main evaluation uses 54 contract-compatible questions derived from official DSBench workbook tables, not the official DSBench questions. Across three repeats, DataProof achieved 95.68% mean accuracy (SD 1.07 percentage points), compared with 62.96% for the offline heuristic baseline. The difference is descriptive because the task templates and model settings do not support an inferential population claim.

There were seven failed runs: four over-clarifications on semantically unusual identifier sums and three incorrect row counts caused by counting non-null values in a selected column. The saved representative traces are in `logs/representative_cases.json`; all failures are in `results/failure_analysis.json`. After diagnosis, the planner instruction made row-count and explicit-total semantics concrete, nullable plan fields were normalized, and transient network errors received bounded retries. An 18-task validation rerun then completed at 100%; the subsequent 36-task three-repeat run was interrupted by prolonged network failures and is not reported as a completed result.

The verifier experiment accepted all 28 clean outputs and rejected all 28 deterministic value corruptions. This demonstrates detection of the tested corruption type only; it does not prove detection of every semantic error. Category tables and exact inputs are stored under `results/`.

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
| G1 | Contract planner | outcome accuracy | No matching base-paper metric | E3 95.68%; no-contract pilot 88.89% | Partially (different evaluation sizes) |
| G2 | Verifier | clean acceptance and corruption recall | No matching base-paper metric | 100% / 100% on 28 controlled cases; natural no-verifier pilot tied | Partially |
| G3 | Clarify/abstain | appropriate ambiguity outcome | No matching base-paper metric | 100% on main ambiguity categories; no-abstention pilot 66.67% overall | Partially |

The DSBench paper reports aggregate data-analysis task success, but its aggregate number must not be placed into the gap table as if it were measured on our selected subset and metrics.

## Changes since Phase 1

The proposal anticipated a Python executor and separate verifier. This implementation uses a constrained JSON operation plan rather than executing model-generated Python, to make local execution safer and contract checks inspectable. The current tool supports common aggregations and simple filters. Phase 1 supervisor feedback was not supplied, so no claim is made that it was addressed. The base paper and three gaps have not been changed.

## Phase checklist and remaining requirements

Phase 1 literature review and proposal drafts are held outside this repository. Their source claims and the supervisor's approval/feedback require student review. A Phase 1 working baseline and initial results were not present in the GitHub repository when this work began.

For Phase 2, the agentic pipeline, logs, three switchable components, web interface, dependency file, secret example, development log, six deterministic tests, DSBench-derived builder, E1-E6 evidence, repeated runs, failure categories, representative traces, architecture diagram and reproduction scripts are present.

The remaining submission-only items are the student-written 8-10 page IEEE/ACM paper, final verification of 25-30 references, assigned project code on the title, Turnitin similarity and AI-writing reports, paper PDF/source ZIP, and Classroom submission. These cannot be generated from the code repository. The post-improvement final rerun also remains incomplete because the API connection stayed in retries for 37 minutes; the completed pre-improvement run is the reported E3 evidence.

The course requires the student to write the paper in their own words. The evidence checklist is in `paper/authoring_checklist.md`. The source-code release and submission should be made only after the real results and final paper have been checked.
