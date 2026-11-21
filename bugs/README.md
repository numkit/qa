# NumKit QA Bug Tracker (`bugs/`)

Triaged divergences and missing-function parity gaps discovered by `fieldtest/` and `parity/`.

## Layout

```text
bugs/
├── README.md                 # This file
├── missing.md                # Absent-function parity gaps sorted by corpus impact
├── open/<module>/<slug>.md   # Active bugs grouped by NumKit module (cas, core, signal, ...)
└── closed/<module>/<slug>.md # Resolved bugs (moved here once fixed + covered by unit test)
```

## Rules

1. **One file per root cause**, not per script. Multiple scripts hitting the same bug are listed under `Affected scripts` (relative corpus paths only).
2. **Never paste third-party corpus source code.** Every bug file must include a minimal, self-contained synthetic repro (2–10 lines of MATLAB) written from scratch.
3. **Required fields in each bug file:**
   - **Module:** target module in `numkit/bundle/modules/` (`cas`, `numkit`, `ops`, `signal`, `stats`, `image`, `comm`, `control`, `wavelet`, `audio`, `value`, `sys`).
   - **Class:** `parse-error` | `runtime-error` | `workspace-mismatch` | `nk-hang` | `error-parity`.
   - **Repro:** minimal standalone MATLAB snippet.
   - **Expected (MATLAB R2025b)** vs **Actual (NumKit)**.
   - **Affected scripts:** list of corpus paths (`corpus/work/...`).
4. **Lifecycle:**
   - Reference open bugs from `fieldtest/groups/*.txt` as `# known: bugs/open/<module>/<slug>.md`.
   - When fixed in `numkit/bundle` (with a unit test) and verified `PASS` in `compare.py`: move the file to `bugs/closed/<module>/<slug>.md` and remove the `# known:` annotation from the group file.
