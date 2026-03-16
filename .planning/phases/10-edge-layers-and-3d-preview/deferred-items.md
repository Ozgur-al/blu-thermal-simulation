# Deferred Items — Phase 10

## Pre-existing Regression Failures (out of scope)

**Issue:** `test_regression_v1.py` fails for `steady_uniform_stack` example:
- Shape mismatch: actual (8, 18, 30) vs baseline (7, 18, 30)
- `examples/steady_uniform_stack.json` has an extra layer compared to when the .npy baselines were generated
- This is an uncommitted modification pre-dating Phase 10-04

**Required fix (not in this plan):** Regenerate baseline .npy files with the updated example:
```bash
python tests/test_regression_v1.py
```
Or revert `steady_uniform_stack.json` to match the baseline.

**Discovered:** Phase 10-04 execution, 2026-03-16
