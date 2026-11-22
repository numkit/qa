# `ilaplace` fails on time-shift exponential factors (`exp(-a*s) * G(s)`)

- **Module:** `cas`
- **Class:** `runtime-error`
- **Status:** closed
- **Date:** 2026-11-22

## Repro

```matlab
syms s t
f = ilaplace(exp(-2*s) / (s*(s + 1)), s, t);
disp(f);
```

## Expected (MATLAB R2025b)

```text
-heaviside(t - 2)*(exp(2 - t) - 1)
```

(Applying the second shifting theorem $\mathcal{L}^{-1}\{e^{-as} G(s)\} = u(t - a)\,g(t - a)$.)

## Actual (NumKit)

```text
Error: ilaplace: could not compute inverse Laplace transform (outside elementary inverse Laplace transform domain) (in call to 'ilaplace') [nk:ilaplace:unevaluated]
```

## Affected scripts

- `corpus/work/Apress--practical-matlab-modeling-w-simulink/PART_1__Chapter_1/iLaplace_Ex7.m`
