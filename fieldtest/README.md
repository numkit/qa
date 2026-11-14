# fieldtest/ — real-world differential testing vs MATLAB

Testing NumKit against **real third-party MATLAB code** (GitHub), run through
both MATLAB R2025b and NumKit (`NUMKIT_BUNDLE_DIR`, defaulting to sibling
`../bundle`), with every divergence classified cleanly. This is deliberately
complementary to:

- `../parity/` — *spec-driven* parity (curated calls, MATLAB R2025b ground
  truth, fingerprint diff);
- unit tests in `modules/*/tests/` — synthetic test suites written alongside the
  implementation.

## Layout

```
fieldtest/
  README.md        this file — the method + the workflow rules
  fetch.py         clone/update catalog repos into corpus/ + prepare work copy
  harness.py       dual-run (MATLAB vs NumKit), classify, report
  reports/         committed run reports (JSON + summary per batch)
  data/            runnable.json, candidates.json, answers.json (COMMITTED —
                   paths + verdicts only, no third-party source text)
  compare.py       comparison groups (R5): a curated group dual-run with a
                   human-readable PASS / KNOWN / NEW report
  groups/          COMMITTED — one group per file: script paths + optional
                   `# known: <id>` annotations
  corpus/          GITIGNORED — cloned repos (corpus/repos/), the prepared
                   work copy (corpus/work/), and the cached catalog.json.
                   Third-party code NEVER enters git.
```

Sources come from the external catalog
[awesome-matlab-books](https://github.com/hotredman/awesome-matlab-books)
(`catalog.json`: companion-code repositories for 75+ MATLAB books across 12
categories). The catalog is cached at `corpus/catalog.json` on first fetch and
reused from cache afterwards, so a batch stays reproducible against the
catalog it was fetched with; `--refresh-catalog` pulls a newer one.

## Workflow

1. **Fetch** — `python fetch.py` clones/updates every catalog repo into
   `corpus/repos/<owner--repo>` (filters: `--category <id>[,<id>]`,
   `--book <id>[,<id>]`; `--list` shows what's available), then prepares
   `corpus/work/`: a UTF-8-transcoded mirror (many real-world files are GBK;
   transcoding gives BOTH engines the same text — MATLAB on a non-Chinese
   locale garbles GBK just like nk does, so the comparison stays fair).

2. **Qualify** — `python harness.py qualify [N] [filter]` harvests heuristic
   candidates (self-contained scripts, static token filter for interactive /
   system / nondeterministic constructs) and then **verifies runnability
   empirically**: each candidate is executed in MATLAB R2025b; the ones that
   run to completion form the run corpus, committed as `runnable.json`.
   Graphics calls are NOT excluded: both engines execute them headless
   (nk runs its graphics system, MATLAB -batch creates invisible
   figures) and the R4 workspace verdict is blind to plots. This replaces
   trusting the static harvest: heuristic filters both miss runnable
   scripts and admit scripts that error in MATLAB (worthless for diffing —
   there is no ground truth to diverge from). Runnable = MATLAB exit 0;
   determinism is still probed later by the double nk run at diff
   time. The catalog of runnable scripts is the stable comparison set
   batches track progress against.

3. **Run** — `python harness.py run [N] [filter]` executes each `runnable.json`
   script through the three engines (timeout-protected, determinism-probed by
   a double nk run), then compares **workspaces via .mat files** (see
   [Comparison semantics](#comparison-semantics)), and writes `reports/` + a
   verdict per script:

   | verdict | meaning | action |
   |---|---|---|
   | `pass` | outputs match numerically | record timings (speed stats) |
   | `runtime-error` / `workspace-mismatch` | nk fails or a numeric variable diverges where MATLAB succeeds | **file a bug** (see below) |
   | `parse-error` | nk's parser rejects valid MATLAB | **file a bug** |
   | `absent-fn` | function not implemented | parity gap (unimplemented function) |
   | `both-error` | both engines error | eyeball: same construct → error-parity PASS; different → bug on the diverging side |
   | `nk-hang` / `matlab-timeout` | hang | bug (hang) |
   | `nondeterministic` | double-run differs | exclude, note in report |

4. **Turn findings into self-contained unit tests.** Runtime/parse divergences
   become minimal inline GoogleTest cases in the corresponding `modules/<pkg>/tests/`
   suite — no `fieldtest/corpus` dependency in committed tests.

5. **Signature audit** — `python ../parity/signprobe.py <fn> [<fn>…]` captures
   MATLAB's documented signature (`help fn`) and NumKit's, diffs them, and
   reports the first divergent line. Batch-audit the functions a corpus batch
   actually used:
   `python ../parity/signprobe.py $(python harness.py used-fns <report>)`.

## Comparison semantics

Results are compared as **workspaces via .mat files**, not as printed text:

- The harness appends `save` to each run — `run('<script>');
  save('out_<engine>.mat')` — in BOTH engines, with cwd set to a per-script
  temp dir (scripts themselves are never modified; the corpus stays
  untouched). A run therefore yields two .mat files: nk's and MATLAB's.
- Both files are read by **scipy.io.loadmat** — an engine-neutral reader.
  Comparing nk's output with nk's own `load` would be circular.
- Compared: **numeric variables present in both files** (intersection).
  Per variable: class bucket (real / complex / logical) and shape must match
  exactly; values compared at rel 1e-9 (the bug playbook's algorithmic
  threshold); NaN == NaN and ±Inf compare equal to themselves. Non-numeric
  variables (char/struct/cell) are listed in the report but not compared —
  MAT type fidelity beyond numeric is out of scope for the diff verdict.
  (Class is compared at bucket level, not dtype level, because MATLAB
  R2025b packs integral-valued doubles into the smallest integer type when
  saving — v6 and v7 alike — and promotes back on load; the stored dtype is
  not a reliable comparison channel.)
- Variables present on only one side are reported as info (a nk error
  mid-script is already a `runtime-error` verdict regardless).
- stdout and exit status are still captured — they drive the
  `parse-error` / `runtime-error` classes and diagnostics — but the numeric
  verdict comes from the workspace. **Print-format divergences (`fprintf`
  formatting, `disp` precision) no longer count as mismatches.**
- Determinism probe: the double nk run is compared via its two .mat
  files (previously: stdout).
- The .mat artifacts are transient (gitignored temp dirs) and never
  committed — they are derivatives of third-party code; reports carry
  variable-level verdicts only.

## Comparison groups (R5)

`compare.py` is the **user-facing** front-end to the same comparison
machinery: a curated group of scripts, one dual-run, a human-readable
report distinguishing filed divergences from new ones.

```
python compare.py --list          # available groups
python compare.py mdadams         # dual-run the group
python compare.py mdadams -v      # + per-variable diff lines
```

- A group is `compare/groups/<name>.txt`: one script path per line
  (relative to `fieldtest/`), optional trailing `# known: <bug-id>`
  marking an already-filed divergence.
- Verdict per script: `PASS` (workspaces match) / `KNOWN (<bug>)`
  (diverges as filed) / `NEW <what>` (divergence not in the catalog —
  the actionable class). Exit code 1 iff any NEW.
- Groups are committed and stable across corpus rebuilds (paths are
  deterministic `owner--repo` names). Groups are cut from
  MATLAB-qualified scripts — qualify first, then curate.
- After a bug fix: remove its `# known:` annotation, re-run the group —
  the fix must turn the script PASS (the group is the family-level
  regression check; the gtest guard is the unit-level one).

## Sources policy

- **The catalog is the ONLY source of repositories.** No supplementary local
  picks — new sources are added to awesome-matlab-books itself (it is a
  curated project for exactly this), then picked up by `fetch.py
  --refresh-catalog`. The local corpus is disposable: `rm -rf fieldtest/corpus`
  must lose nothing that isn't rebuildable or already distilled into a bug
  file.
- Source of truth: the awesome-matlab-books catalog (CC BY-SA 4.0 as a
  compilation). Per-repo licenses vary — book companion code is often
  all-rights-reserved with no LICENSE file; that is acceptable here because:
- `corpus/` is gitignored; third-party code is never committed, shipped, or
  redistributed — only executed for testing. Reports contain paths + verdicts,
  not third-party source text. The cached `catalog.json` stays under
  `corpus/` for the same reason.
- `python_companions` (books whose companion code is Python) are deliberately
  not fetched.

## Speed measurement rules

- Report wall time per engine per script, but **subtract the MATLAB batch
  startup** (measured ≈3.2 s on this machine) for compute comparisons.
- Startup-dominated scripts (< 1 s MATLAB compute) are excluded from speed
  claims; the speed table is built from `pass` verdicts only (comparable
  work), and reports both nk builds (WASM = the npm artifact, native =
  the engine ceiling).
