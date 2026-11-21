# Missing Functions (`absent-fn`)

Tracked parity gaps discovered by `fieldtest/`, sorted by corpus impact.

| Function | Module | Affected scripts (known so far) | Notes |
|---|---|---|---|
| `pretty` | `cas` | 6 (`mdadams`: `differentiation_1.m`, `integration_1.m`, `iult_1.m`, `ult_1.m`, `example_6.m`, `example_7.m`) | Pretty-print symbolic expressions in ASCII art |
| `matlabFunction` | `cas` | 3 (`practical-modeling`: `Example5_2ndODE.m`; `practical-modeling-ode`: `RK_2ndODE_ex1.m`, `RK_2ndODE_ex2.m`) | Convert symbolic expression to anonymous function handle / `.m` file |
| `decic` | `numkit` (ODE) | 3 (`practical-modeling-ode`: `IMPLICIT_2ODE_EX3.m`, `DOUBLE_Pedulum_Linear_2.m`, `DOUBLE_Pedulum_Model_2.m`) | Consistent initial conditions for implicit ODEs (`ode15i`) |
| `bvpinit` | `numkit` (ODE) | 1 (`practical-modeling-ode`: `BVP_EX1.m`) | Initial guess structure for boundary value problems (`bvp4c`/`bvp5c`) |
