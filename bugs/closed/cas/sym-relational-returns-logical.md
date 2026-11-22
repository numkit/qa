# Symbolic relational operators (`==`, `~=`, `<`, `>`) return `logical` instead of `sym`

- **Module:** `cas`
- **Class:** `workspace-mismatch` / `runtime-error`
- **Status:** closed
- **Date:** 2026-11-22

## Repro

```matlab
syms x
e = (x^2 == 4);
fprintf('class=%s val=%s\n', class(e), char(e));
```

## Expected (MATLAB R2025b)

```text
class=sym val=x^2 == 4
```

`x^2 == 4` constructs a symbolic equation of class `sym` (which can then be passed to `solve`, `dsolve`, `lhs`, `rhs`, `char`, etc.).

## Actual (NumKit)

- `e = (x^2 == 4)` evaluates to `logical` (`false`), with `isa(e, 'sym') == 0`.
- Calling `char(e)` fails with:
  ```text
  Error: Cannot convert to char (in call to 'char') [numkit:char:unsupportedType]
  ```
- Downstream calls like `solve(x^2 + y^2 == a, ...)` receive `logical` operands instead of symbolic equations.

## Affected scripts

- `corpus/work/mdadams--sigsysbook_companion/slides/matlab/examples/example_6.m`
- `corpus/work/mdadams--sigsysbook_companion/slides/matlab/examples/example_7.m`
