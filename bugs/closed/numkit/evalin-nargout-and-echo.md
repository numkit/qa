# `evalin('caller', ...)` ignores `nargout` for `who` and echoes unsemicoloned expressions

- **Module:** `numkit`
- **Class:** `runtime-error` / `workspace-mismatch`
- **Status:** closed
- **Date:** 2026-11-22

## Repro

```matlab
% probe_evalin.m
function probe_evalin()
    ws = evalin('caller', 'who');
    fprintf('who_class=%s who_numel=%d\n', class(ws), numel(ws));
    v = evalin('caller', 'a');
    fprintf('v=%g\n', v);
end
```

```matlab
a = 42;
probe_evalin();
```

## Expected (MATLAB R2025b)

```text
who_class=cell who_numel=1
v=42
```

1. `ws = evalin('caller', 'who')` returns a cell array of variable names without printing to stdout.
2. `v = evalin('caller', 'a')` assigns `v` silently without printing `a = 42` to stdout (even when the evaluated string has no trailing semicolon).

## Actual (NumKit)

1. `ws = evalin('caller', 'who')` prints:
   ```text
   Your variables are:

   a
   ```
   and leaves `ws` unassigned, failing on the next line with:
   ```text
   Error: Undefined function or variable 'ws'
   ```
2. `v = evalin('caller', 'a')` (when called on an existing variable) prints `a = 42` to stdout unless the string explicitly ends with `;` (`evalin('caller', 'a;')`).

## Affected scripts

- (Discovered while implementing the CAS workspace sidecar dumper in `fieldtest/harness.py`.)
