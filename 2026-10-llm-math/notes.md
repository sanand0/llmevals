# Investigation notes

- 2026-10-13: Moved the multiplication experiment from `~/code/llmevals/multiplication/`, preserving all original raw results and the original batch logs.
- Earlier duplicate API runs were caused by remote command replay/timeout; raw data includes duplicates for cost auditing. New runner must use file locking and resume by exact problem key.
- Key observation: output-token caps confound arithmetic accuracy; report empty replies and timeout separately, and compare 4,096 vs 12,000/20,000 token conditions.

- Follow-up: final 50-digit GPT-6.1 Sol trials (5 missing from prior partial run) were attempted through OpenRouter; all five returned HTTP 402 insufficient credits. They were preserved as terminal error observations, not counted as arithmetic mistakes.
- The raw `correct` field reflects an early strict-output scorer for some exploratory batches. It incorrectly marked numerically correct explanations wrong; `analyze.py` now rescans raw `answer` strings uniformly and computes `correct` independently. Kept original raw rows immutable.
- Snapshot pricing taken from public OpenRouter model catalog. Pricing for errored/timed-out attempts cannot reliably be reconstructed. Summed recorded successful attempts (including duplicates) are estimated ~$16.42; OpenRouter bill may differ.
- Implemented an explicit 712-request plan, exact per-case identity, a `flock` to avoid concurrent paid runs, append-only raw data, error-preserving cache, an explicit `just retry-errors`, and `just build` which skips all cached API calls.
- Local tests cover deterministic operand generation, zero-repeat cached builds, deletion/full reschedule dry-run, interruption/one-case resume, scoring oracle, plus analysis regeneration without API calls.
- 2026-10-13: Relocated complete experiment to `~/code/llmevals/2026-10-llm-math/` at user request; updated repository README indexes. No trial data or configuration changes.
- 2026-10-13: `just retry-credits` added 40 attempts (10 HTTP 402, then 25 HTTP 401, then five successful API calls with empty final replies after using all 4,096 output tokens). The five once-credit-blocked 50-digit Sol problems now have recorded API responses but no exact answers. Totals: 961 attempts, ~US$16.62 identifiable token charges. Updated stale report and assertion. Retry logic now uses the newest error unless a successful API response exists, avoiding repeatedly treating a subsequent 401 as a 402.
