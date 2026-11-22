# `dsolve` fails on simple 1st-order linear homogeneous ODE (`'Dy = -5*y'`)

- **Module:** `cas`
- **Class:** `runtime-error`
- **Status:** closed
- **Date:** 2026-11-22

## Repro

```matlab
y = dsolve('Dy = -5*y', 'y(0)=1', 't');
disp(y);
```

## Expected (MATLAB R2025b)

```text
exp(-5*t)
```

## Actual (NumKit)

```text
Error: dsolve: could not solve 1st-order ODE (ODE outside supported 1st-order classes or uncertified) (in call to 'dsolve') [nk:dsolve:failed]
```

## Affected scripts

- `corpus/work/Apress--practical-matlab-modeling-w-simulink/PART_1__Chapter_4/STIFF_1ODE_a.m`
- `corpus/work/Apress--practical-matlab-modeling-w-simulink/PART_1__Chapter_4/STIFF_1ODE_EX1.m`
