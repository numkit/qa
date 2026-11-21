# `dsolve` fails to parse comma-separated initial conditions in a single string (`'y(0)=0, Dy(0)=0'`)

- **Module:** `cas`
- **Class:** `parse-error`
- **Status:** open
- **Date:** 2026-11-22

## Repro

```matlab
y = dsolve('D2y = -sin(t)', 'y(0)=0, Dy(0)=0', 't');
disp(y);
```

## Expected (MATLAB R2025b)

```text
sin(t) - t
```

MATLAB accepts multiple comma-separated initial conditions inside a single string argument (legacy string API).

## Actual (NumKit)

```text
Error: dsolve: parse error in 'y(0)=0, Dy(0)=0': unexpected token after expression (in call to 'dsolve') [nk:dsolve:parseError]
```

## Affected scripts

- `corpus/work/Apress--practical-matlab-modeling-w-simulink/PART_1__Chapter_3/Adams_Moulton_2ndODE_ex1.m`
- `corpus/work/Apress--practical-matlab-modeling-w-simulink/PART_1__Chapter_3/RK_2ndODE_ex3.m`
- `corpus/work/Apress--practical-matlab-modeling-w-simulink/PART_1__Chapter_3/RK_2ndODE_ex4.m`
