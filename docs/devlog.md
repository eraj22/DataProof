# Development log

| Date | Observed issue | Change | Measured effect |
|---|---|---|---|
| 2026-11-07 | No runnable Phase 1 repository or baseline was present. | Added a constrained tabular pipeline, a local web interface, JSON trajectories, an offline baseline, and deterministic tests. | Four unit tests passed. The offline pilot results are in `results/` after running the command in the README; they are not DSBench results. |
| 2026-11-07 | Initial web template used string formatting on CSS braces. | Changed result insertion to a literal placeholder replacement. | Web page renders without formatting exceptions in a local GET check. |
| 2026-11-07 | Groq calls returned Cloudflare 1010 with Python's default HTTP signature, then a 404 for the configured model. | Added an application user agent, classified provider failures as errors, and selected an available model from the account's model list. | Connectivity and model access were confirmed; the subsequent pilot result is recorded separately. |
| 2026-11-07 | The first no-contract ablation hit Groq's 8,000 tokens/minute limit on two pilot calls. | Increased bounded retries and spaced Groq requests by four seconds in the experiment runner. | The paced rerun completed 27 calls without service errors; accuracy was 8/9 in each repeat versus 9/9 for the full system. This is only a synthetic pilot result. |

Further entries require actual Groq and DSBench runs. Record failures, changes, and before/after measurements here.
