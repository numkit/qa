# Symbolic functions (`symfun`): `syms y(t)` and `f(x) = expr` not supported

- **Module:** `cas`
- **Class:** `runtime-error`
- **Status:** closed
- **Date:** 2026-11-22

## Repro

```matlab
% Case 1: declaring a symbolic function via syms
syms y(t)
fprintf('class=%s val=%s\n', class(y), char(y));

% Case 2: defining a symbolic function via indexed assignment
syms x
f(x) = x^2 + 1;
fprintf('class=%s val=%s\n', class(f), char(f));
```

## Expected (MATLAB R2025b)

- Case 1: `class=symfun val=y(t)` (also creates symbolic variable `t` in caller workspace).
- Case 2: `class=symfun val=x^2 + 1`.

## Actual (NumKit)

- Case 1:
  ```text
  Error: syms: 'y(t)' is not a valid variable name (in call to 'syms') [nk:syms:invalidIdentifier]
  ```
- Case 2:
  ```text
  Error: double: symbolic expression 'x' contains unresolved symbols or cannot be evaluated to double (in array indexing) [nk:sym:unresolvedSymbol]
  ```

## Affected scripts

- `corpus/work/Apress--practical-matlab-modeling-w-simulink/PART_1__Chapter_1/Laplace_vs_Dsolve_Ex6.m`
- `corpus/work/Apress--practical-matlab-modeling-w-simulink/PART_1__Chapter_1/Laplace_vs_Dsolve_New_MATLAB_ex4.m`
- `corpus/work/Apress--practical-matlab-modeling-w-simulink/PART_1__Chapter_1/Laplace_vs_Dsolve_New_MATLAB_ex5.m`
- `corpus/work/Apress--practical-matlab-modeling-w-simulink/PART_1__Chapter_2/Example1.m`
- `corpus/work/Apress--practical-matlab-modeling-w-simulink/PART_1__Chapter_2/Example2.m`
- `corpus/work/Apress--practical-matlab-modeling-w-simulink/PART_1__Chapter_2/Example4.m`
- `corpus/work/Apress--practical-matlab-modeling-w-simulink/PART_1__Chapter_2/ExampleODE1.m`
- `corpus/work/Apress--practical-matlab-modeling-w-simulink/PART_1__Chapter_3/Example1_2ndODE.m`
- `corpus/work/Apress--practical-matlab-modeling-w-simulink/PART_1__Chapter_3/Example2_2ndODE.m`
- `corpus/work/Apress--practical-matlab-modeling-w-simulink/PART_1__Chapter_3/Example3_2ndODE.m`
- `corpus/work/Apress--practical-matlab-modeling-w-simulink/PART_1__Chapter_3/Example4_2ndODE.m`
- `corpus/work/Apress--practical-matlab-modeling-w-simulink/PART_1__Chapter_4/STIFF_1ODE_EX3.m`
- `corpus/work/mdadams--sigsysbook_companion/slides/matlab/examples/example_6.m`
