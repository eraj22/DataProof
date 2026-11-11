param(
  [Parameter(Mandatory=$true)][string]$DSBenchDataRoot,
  [int]$RequestDelay = 4
)
$ErrorActionPreference = "Stop"
if (-not $env:GROQ_API_KEY) { throw "Set GROQ_API_KEY in this PowerShell session." }
python data/build_dsbench_derived.py --dsbench-root $DSBenchDataRoot --output data/dsbench_derived --tables 7
python -m unittest discover -s tests -v
python experiments/run_eval.py --manifest data/dsbench_derived/manifest.json --mode E1 --split test --repeats 3 --output results/E1_dsbench_derived_final.json
python experiments/run_eval.py --manifest data/dsbench_derived/manifest.json --mode E3 --split test --repeats 3 --request-delay $RequestDelay --output results/E3_dsbench_derived_final.json
python experiments/run_verifier_eval.py --manifest data/dsbench_derived/manifest.json --split test --output results/E4_verifier_fault_injection.json
python experiments/analyze_phase2.py
