# `solve` does not accept multiple equation arguments (`solve(eq1, eq2, [x y])` / `solve(eq1, eq2, x, y)`)

- **Module:** `cas`
- **Class:** `runtime-error` / `workspace-mismatch`
- **Status:** closed
- **Date:** 2026-11-22

## Repro

```matlab
syms x y

% Works today (2 args: vector of equations + vector of variables):
[sx, sy] = solve([x + y - 3, x - y - 1], [x y]);

% Case 1: separate equation args + vector of variables, multiple outputs
[sx1, sy1] = solve(x + y - 3, x - y - 1, [x y]);

% Case 2: separate equation args + vector of variables, struct output
s = solve(x + y - 3, x - y - 1, [x y]);

% Case 3: separate equation args + separate variable args
[sx2, sy2] = solve(x + y - 3, x - y - 1, x, y);
```

## Expected (MATLAB R2025b)

- Case 1: `sx1 = 2`, `sy1 = 1`
- Case 2: struct with fields `s.x = 2`, `s.y = 1`
- Case 3: `sx2 = 2`, `sy2 = 1`

## Actual (NumKit)

- Case 1: `Error: Too many output arguments. (in call to 'solve')` (or `solve: too many input arguments — at most 2 accepted (got 3). [numkit:solve:maxnargin]` when combined with `==` equations).
- Case 2: returns `[empty sym]` instead of a solution struct.
- Case 3: `Error: solve: too many input arguments — at most 2 accepted (got 4). (in call to 'solve') [numkit:solve:maxnargin]`.

## Affected scripts

- `corpus/work/Apress--Simulation-of-Power-Electronics-Circuits-with-MATLAB-Simulink/Chapter8_Code1.m`
- `corpus/work/Apress--Simulation-of-Power-Electronics-Circuits-with-MATLAB-Simulink/Chapter8_Code3.m`
- `corpus/work/Apress--Simulation-of-Power-Electronics-Circuits-with-MATLAB-Simulink/Chapter9_Code1.m`
- `corpus/work/Apress--Simulation-of-Power-Electronics-Circuits-with-MATLAB-Simulink/Chapter9_Code2.m`
- `corpus/work/mdadams--sigsysbook_companion/slides/matlab/examples/example_7.m`
