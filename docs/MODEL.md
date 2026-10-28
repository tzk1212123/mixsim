# Model, equations and provenance

This reduced-order simulator supports the proposal's semester color-matching task, software integration and fault-handling demonstration. All outcomes are simulated. Citing a real device specification does not establish bench calibration.

## Authoritative sources

Sources checked on October 27, 2026. The supplied local NE-1000 manual is the authority for the two implemented syringe profiles; no actual bench syringe was specified.

| Item | Value or relation used | Source and scope |
|---|---|---|
| NE-1000 default syringe profile | HSW Norm-Ject, 10 mL, 15.9 mm internal diameter; 8.349 uL/hr minimum, 607.6 mL/hr maximum | Supplied NE-1000 Syringe Pump User Manual, V3.923, section 12.7, printed page 50. Approximately 0.13915 to 10126.67 uL/min; the actual bench syringe is unconfirmed. |
| NE-1000 alternative profile | B-D, 10 mL, 14.43 mm internal diameter; 6.876 uL/hr minimum, 500.4 mL/hr maximum | Same manual/table. Converted range: 0.1146 to 8340 uL/min. Both pumps share the selected profile. |
| Syringe diameter setting | 0.1..50.0 mm; only while stopped | Same manual, section 7.1, printed page 12. The simulator selects fixed table profiles at startup rather than emulating DIA or live diameter changes. |
| USB-6003 analog input | 16-bit ADC, +/-10 V range | [NI device specifications](https://docs-be.ni.com/bundle/usb-6003-specs/raw/resource/enus/374372a.pdf). Only quantization is represented; not the full accuracy budget, common-mode behavior or wiring. |
| USB-6003 sample capability | 100 kS/s aggregate maximum | Same NI specification. This simulator samples once per integration step, normally 10 Hz, not at the hardware maximum. |
| Water viscosity | 0.00089 Pa s at 25 C, rounded | [NIST water and steam viscosity reference](https://srd.nist.gov/JPCRD/jpcrd243.pdf). Temperature is fixed and dilute dyes are approximated as water. |
| Hydraulic resistance | Hagen-Poiseuille relation | [Weizmann Institute instructional material](https://www.weizmann.ac.il/mcb/kam/sites/mcb.kam/files/uploads/6c.Romantic-Phys%2CChem.pdf). Assumes laminar Newtonian flow in a rigid circular tube; a separate assumed first-order pressure lag is added. |
| Absorption | Beer-Lambert form | [IUPAC definition](https://goldbook.iupac.org/terms/view/B00626). The physical law describes narrow-band radiation; using three hypothetical camera channels is a simplifying approximation, not measured dye spectroscopy. |
| MCP | Official Python SDK 1.x FastMCP, explicitly constrained below 2 | [Official v1.x SDK](https://github.com/modelcontextprotocol/python-sdk/tree/v1.x). The installed version is recorded in requirements-lock.txt. |

## Explicit demonstration assumptions

| Parameter | Default | Interpretation |
|---|---|---|
| Selected syringe / initial fill | HSW Norm-Ject 10 mL; initially 10000 uL each | Brand/diameter/rates are an explicit manual-table profile; choosing it for the bench remains an assumption. syringe_capacity_ul means initial fill and cannot exceed nominal capacity. |
| Command envelope | 1000 uL/min per pump; 1500 uL/min combined | Assumed project limits below the example device maximum, not approval for physical operation. |
| Equivalent circular tube | Length 0.5 m; internal radius 0.15 mm | Assumed flow resistance, not the professor's chip geometry. |
| Transport volume | 35.3429 uL | Initially calculated from pi*r^2*L. Configurable independently as an effective dead volume. |
| Mixing volume | 30 uL | Assumed perfectly mixed observation chamber; no CFD or real microfluidic mixing claim. |
| Pump time constant | 1 s | Illustrative lag, not measured NE-1000 response. |
| Pressure time constant | 0.5 s | Lumped lag, not an elastic-tube or motor model. |
| Pump calibration | Fixed per-pump Gaussian bias, standard deviation 2% per seed | Assumption, not the manufacturer's accuracy specification. |
| Pressure transducer | 0-100 kPa maps to 0-5 V; noise sigma 0.08 kPa | Hypothetical external transducer. The NI DAQ itself measures voltage. |
| Pressure interlock | Trip at 60 kPa; reset below 5 kPa | Assumed project thresholds requiring review against all actual component ratings. |
| Camera | Mean of 5 frames; per-frame per-channel noise sigma 0.6 DN | Synthetic ROI model; no exposure drift, white-balance drift or real images. |
| Stock optical densities | A=(0.05,0.45,1.4); B=(1.5,0.4,0.08) | Synthetic amber and blue coefficients, not measured food-dye absorption. |
| Camera white reference | (245,245,245) DN | Assumed linear channel response, not calibrated sRGB. |
| Success tolerance | RGB RMSE <=3 DN | Demonstration convention, not a measured hardware requirement. |

## Device capability versus project limits

`config.syringe_profile` selects an immutable entry in `syringes.py`; it determines manufacturer, nominal capacity, inside diameter and the nonzero device flow range. Supported IDs are `hsw_norm_ject_10ml` and `bd_10ml`. `configs/bd-10ml.json` selects the second profile. No interpolation or capacity-only inference is used.

The manual's hourly rate columns are converted to uL/min; its separately rounded mL/min maximum is not used as a second boundary. Project per-pump/combined limits remain configurable, explicitly assumed limits. A project maximum cannot exceed the selected device capability. At command time, device maximum overflow, project maximum overflow and below-minimum flow have distinct errors. Exported JSON records both the configuration ID and resolved syringe specification/source.

The model still does not implement RS-232 packets, DIA/RAT/RUN/STP semantics, withdrawal, rate quantization or motor stall. A zero flow command is an API stop convention. The external 60 kPa pressure interlock is not a substitute for the manual's motor-stall behavior. Pump response, noise and calibration bias remain assumptions.

## Equations and units

API flow is in uL/min, time in seconds, pressure in kPa, and remaining liquid in uL. Hydraulic calculations convert to SI.

1. Each pump's target delivered flow is `q_target = q_command * fixed_bias`. Update using `q_next = q + (q_target-q)*(1-exp(-dt/tau_pump))`. Actual delivered volume depletes the finite syringe. This discretization does not model stepper-motor mechanics.
2. Convert total flow with `Q = (qA+qB)*1e-9/60` in cubic meters per second. Equilibrium gauge pressure is `P_eq = 8*mu*L*Q/(pi*r^4)*clog_factor` in Pa, followed by an assumed first-order lag. At 400 uL/min, the default equilibrium pressure is approximately 14.9 kPa. A sixfold resistance increase exceeds the assumed 60 kPa trip threshold.
3. A volume-based FIFO models plug-flow transport. A change in flow changes residence time. Stopped fluid does not advect. The line and chamber initially contain 50/50 mixture; dry-tube priming and bubbles are not represented.
4. The mixing chamber's A fraction is updated by `f_next = f + (f_in-f)*(1-exp(-dV/V_mix))`. This assumes complete mixing. Real laminar microfluidic chips can have spatial gradients, limited diffusion and complex residence-time distributions.
5. For synthetic camera channel j: `OD_j = f*OD_Aj + (1-f)*OD_Bj`, then `I_j = white_j * 10^(-OD_j)`. Add independent frame noise, clip to 0-255 and average the frames.
6. The objective is `sqrt(mean((measured_RGB-target_RGB)^2))`, in RGB digital numbers. This is not chemical yield, percentage accuracy or perceptual Delta E.

Each record includes an approximate washout recommendation: `5*tau_pump + (V_transport+6*V_mix)*60/total_flow`. It is a model-based heuristic, not a settling certificate. Default 60 s at 400 uL/min exceeds the recommendation. Low flow requires longer settling, potentially beyond the 600 s operation limit.

## Safety semantics

Both flow commands are validated before either changes. Negative values, nonfinite numbers, booleans used as numbers, pump/combined limits and read-only writes are rejected. Every integration step samples the noisy, quantized DAQ reading and evaluates the interlock independently of the planner.

On a fault, the simulator sets commanded and actual flows to zero immediately. Pressure then decays according to the assumed time constant. Real tubing can retain pressure under a blockage and a real pump can have braking delay. This is not a deployable physical safety system.

Reset requires stopped pumps, low pressure, a cleared injected clog and nonempty syringes. Clearing the clog alone does not clear the latch. Experiment operations stop pumps in a finally block. An aborted record may contain a low final pressure after decay; its triggering pressure is retained in the event log.

## Reproducibility and evaluation

Calibration, DAQ noise, camera noise and random-planner sampling use separate random generators. Passive snapshots and browser polling draw no samples. An explicit camera read does draw fresh samples, so replay requires the same operation sequence as well as the same seed/configuration.

The feedback baseline bisects the commanded A fraction using the signed projection of measured RGB minus target RGB onto the stock-color direction. It does not read true mixture fraction or hidden pump bias. The random baseline samples A fractions between 0.02 and 0.98. Neither is BO, OFAT or an LLM.

Targets lie on the nominal two-stock mixture curve, not anywhere in RGB space. Finite bisection approaches endpoint targets without reaching them exactly. Noise and the pump minimum rate can prevent arbitrary accuracy.

Finalization reruns one explicitly recommended successful trial at the same flows and settling time, with new measurements. `final_record` identifies delivered performance. It is not the best of several replicates, and one campaign is not a statistical benchmark. Multi-seed statistics, confidence intervals and sim-to-real error require additional evaluation and hardware data.
