# Linear indexing `H(2)` on a MISO/MIMO `tf` object throws index out of bounds

- **Module:** `control`
- **Class:** `runtime-error`
- **Status:** closed
- **Date:** 2026-11-22

## Repro

```matlab
A = [-1 0; 0 -2];
B = [1 0; 0 1];
C = [1 1];
D = [0 0];
H = tf(ss(A, B, C, D));
h1 = H(1);
h2 = H(2);
disp(size(H));
```

## Expected (MATLAB R2025b)

`H` is a 1×2 `tf` transfer-function array (`size(H) == [1 2]`). `H(1)` and `H(2)` extract the two SISO transfer functions (`1/(s + 1)` and `1/(s + 2)`).

## Actual (NumKit)

```text
Error: Index 2 exceeds array size 1 (in function call)
```

## Affected scripts

- `corpus/work/Apress--Simulation-of-Power-Electronics-Circuits-with-MATLAB-Simulink/Chgapter8_Code2.m`
