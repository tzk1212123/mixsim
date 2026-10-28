# Virtual syringe pump operating reference

Two infusion-only NE-1000-inspired pumps share one immutable syringe profile per session. Query list_devices or read_device for the active manufacturer, nominal capacity, inside diameter and device flow range. This is not an NE-1000 serial-protocol implementation.

Manual source: NE-1000 Syringe Pump User Manual, firmware V3.923, section 12.7, printed page 50. Supported representative entries:

| Profile | Manufacturer | Capacity | Inside diameter | Minimum rate | Maximum rate |
|---|---|---|---|---|---|
| hsw_norm_ject_10ml (default) | HSW Norm-Ject | 10 mL | 15.9 mm | 8.349 uL/hr | 607.6 mL/hr |
| bd_10ml | B-D | 10 mL | 14.43 mm | 6.876 uL/hr | 500.4 mL/hr |

The minimum and maximum depend on the selected syringe, not capacity alone. API flow is in uL/min: divide minimum uL/hr by 60; multiply maximum mL/hr by 1000/60. The manual's mL/min column is rounded separately; this model consistently converts from its mL/hr column. These table entries are examples, not confirmation of the actual bench syringes.

Device capability and the project envelope are separate. Defaults remain 1000 uL/min per pump and 1500 uL/min combined; these are assumed project limits. Configuration rejects a project maximum outside the selected syringe's device range. A command exceeding the device range returns device_flow_limit; one exceeding only the project maximum returns flow_limit; below-minimum nonzero flow returns flow_minimum. Query active limits rather than assuming the defaults.

flow_ul_min is the commanded flow and remaining_ul is read-only. Set both pumps atomically with set_flows. A single-pump write still checks the combined-flow limit. Zero is the simulator's stop-command convention, not a claim that serial RAT 0 starts a real pump.

Select the syringe profile at configuration/startup time. The profile's diameter is fixed for that session. This model does not yet emulate DIA commands, live syringe changes, serial rounding/precision, withdrawal or motor-stall mechanics. The manual permits diameter settings only while stopped and within 0.1..50.0 mm; both supported profiles are within that range. No arbitrary diameter/rate extrapolation is implemented.

The configured syringe_capacity_ul is the initial liquid fill in each reservoir and cannot exceed the profile's nominal capacity. It may be smaller. Calibration bias (2% standard deviation per seed) and a 1 s pump-response time constant remain assumptions, not manual specifications. No fluid moves without virtual time advancement.

The external simulated pressure interlock defaults to 60 kPa trip and reset below 5 kPa. It is separate from the real pump's motor-stall detection. Neither threshold is an NE-1000 manufacturer safety rating. On a latched fault, stop, let pressure decay, have the operator clear the injected clog, then reset. Reset does not refill liquid.

run_experiment sets flow, advances virtual time, captures a camera measurement and stops both pumps. Default settling is 60 s at 400 uL/min total. Low flow needs longer washout. Dynamic flow/pressure response, immediate stopping and pressure relief remain idealized and require independent bench validation.
