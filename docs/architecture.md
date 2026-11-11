# DataProof architecture

```mermaid
flowchart LR
  U[CSV/XLSX and question] --> P[Profiler]
  P --> C[Contract planner via Groq]
  C -->|missing intent| D{Decision controller}
  C --> V[Schema and contract validator]
  V --> X[Allowlisted pandas executor]
  X --> I[Independent recomputation and provenance verifier]
  I -->|pass| D
  I -->|fail| D
  D --> A[Answer]
  D --> Q[Clarification]
  D --> S[Abstention/error]
  P --> L[JSON trajectory]
  C --> L
  V --> L
  X --> L
  I --> L
  D --> L
```

The model proposes structured JSON and never executes arbitrary code. The executor allows only count, sum, mean, median, minimum, maximum and distinct-count operations, up to four filters, and at most two grouping columns. The verifier recomputes the requested result and records the source columns and row count. Each state transition is timestamped.

## Gap mapping

| Gap | Component | Switch |
|---|---|---|
| Semantic compliance | JSON contract plus validator | `Config(contract=False)` changes planner instruction |
| Evidence-backed acceptance | recomputation verifier | `Config(verifier=False)` |
| Unsafe action under ambiguity | clarification/abstention controller | `Config(abstention=False)` |

The switches are exposed through the experiment runner. Safety validation remains enabled when the contract prompt is ablated so an ablation cannot make the local executor run arbitrary operations.
