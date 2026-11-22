# Arithmetic between complex numeric scalar and `sym` fails (`1i * x`)

- **Module:** `cas`
- **Class:** `runtime-error`
- **Status:** closed
- **Date:** 2026-11-22

## Repro

```matlab
syms x
z = 1i * x;
fprintf('class=%s val=%s\n', class(z), char(z));
```

## Expected (MATLAB R2025b)

```text
class=sym val=x*1i
```

## Actual (NumKit)

```text
Error: Cannot convert complex with nonzero imaginary part to double scalar (in operator '*')
```

NumKit attempts to coerce the complex numeric operand (`1i`) to a real `double` scalar instead of promoting it to a symbolic complex constant before applying symbolic `*` (and likely `+`, `-`, `/`, `^`).

## Affected scripts

- (Discovered during CAS harness verification; affects any symbolic script using complex constants like `1i*w`, `exp(1i*x)`.)
