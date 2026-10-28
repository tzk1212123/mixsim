# Pytest plan

Start with the six functions in `test/test_rig.py`: valid flow, zero flow, negative flow, per-pump limits, combined limits and invalid types. The student's initial valid-flow and zero-flow functions are preserved. The optional advanced checks are saved in `test/advanced_checks.py` and are not collected by default. Run them later with `python -m pytest test/advanced_checks.py -v`. The checklist below is a roadmap for later study, not a requirement to learn everything at once.

Install `pip install -e ".[dev,mcp]"` and run `python -m pytest -v`. Source and test paths are configured in pyproject.toml. The introductory suite reports six tests; each function checks several inputs with assertions.

## Priority 1: driver envelope

Entry point: `from mixsim import Rig, RigConfig, RigError`. Use a new instance per case.

- Valid commands succeed; zero is a stopped pump.
- Parameterize negative, over-limit, combined-over-limit and below-minimum nonzero rates, NaN, infinities, strings, None and booleans.
- Atomicity: if one rate is invalid, neither command changes.
- A single pump-channel write still checks the combined-flow envelope.
- DAQ pressure, temperature and heater writes all return read_only errors.
- Unknown devices, channels and operations fail explicitly.
- Inject clog factor 6, request 200/200 uL/min and advance; verify an overpressure event, two stopped pumps and a latched fault.
- Nonzero writes fail while latched; stop and zero commands remain available.
- Reset fails with high residual pressure, an injected clog or running pumps.
- Clear the clog and let pressure decay, then explicitly reset. Clearing a clog alone must not clear the latch.
- Use a smaller configured syringe capacity to verify depletion, stop and lack of free refill.
- Advance rejects zero, negative, over-600-second and nonfinite durations without advancing time.

## Syringe-profile checks

- The default HSW Norm-Ject 10 mL profile reports 15.9 mm diameter, a 0.13915 uL/min minimum and a 607.6*1000/60 uL/min maximum.
- The B-D 10 mL profile reports 14.43 mm diameter, a 0.1146 uL/min minimum and an 8340 uL/min maximum.
- A 0.12 uL/min command is accepted for B-D but rejected for HSW. Zero remains a valid stop command for either profile.
- Reject unknown profile IDs and initial fill above nominal capacity. A smaller initial fill remains valid.
- Reject a project maximum above the selected device capability; project limits and device capability must be reported separately.
- Runtime errors distinguish device_flow_limit, flow_limit (project limit), flow_minimum and total_flow_limit. Rejected writes remain atomic.
- Configuration JSON round-trips with the selected profile. Device reads, active pump references and run exports agree on the profile/diameter/range.
- Changing a profile requires constructing a new configuration/session; arbitrary live diameter changes and serial-protocol fidelity are not implemented.

## Priority 2: model behavior

Entry points: mixsim.physics.pressure_kpa, color_rgb and color_error.

- Independently check flow-unit conversion; uL/min must not be treated as mL/min.
- Pressure scales linearly with flow and viscosity and inversely with the fourth power of radius.
- No advection occurs while stopped. Delivered volume depletes finite reservoirs; use a justified integration tolerance.
- Color does not jump immediately after a recipe change: transport delay and mixing lag remain visible.
- With noise and calibration bias disabled, a flushed mixture approaches independently calculated optical output.
- Identical seed, configuration and explicit operation sequence reproduce output; another seed changes noise/calibration.
- Inserting any number of snapshot/public_state calls must not change later readings.
- Explicit camera reads draw fresh noise; they are not passive polling.
- Repeated DAQ reads return the cached sample. Zero flow can retain noise and quantization, so pressure need not be exactly zero.
- RGB consists of three finite channels in 0-255. Error is RGB RMSE, not perceptual Delta E.
- Invalid configurations fail before running, including negative noise, nonfinite parameters and inconsistent thresholds.

## Priority 3: campaign integrity

Entry point: `from mixsim.service import LabService`.

- Experiment records are complete and pumps stop afterward; overpressure retains an aborted record.
- Only a successful trial can be recommended. Reject missing, aborted, out-of-range and noninteger record IDs.
- Finalization without a recommendation fails.
- Finalization repeats the selected flows and settling time with a new record/measurement, kind replicate and recommended_from linkage.
- Successful finalization prevents further trials/finalization in that campaign. An aborted replicate must not mark completion.
- New exploration after recommendation invalidates that recommendation.
- External dispatch cannot forge kind=replicate.
- JSON exports preserve configuration, seed, target, all records, faults and caller sources. Never replace the final replicate with a better observed trial.
- MCP exposes neither hidden truth nor built-in optimization.
- Targets lie on the two-stock optical mixture curve; do not assume two stocks span arbitrary RGB colors.

## Priority 4: caller parity and protocol

HTTP entry point: `mixsim.web.make_server(port=0, service=lab)` permits an ephemeral port. Run in a background thread and clean up with shutdown/server_close. MCP entry point: `mixsim.mcp_server.create_server(url=...)`.

- Equivalent invalid commands through Python, CLI/HTTP and MCP return matching driver error codes without modifying commands.
- MCP experiments appear in the same HTTP session, rather than a second LabService.
- Exercise MCP initialization, discovery, three reference resources, resource reads and valid/invalid tool calls through the actual protocol, not only direct Python calls.
- Tool discovery must exclude fault injection, session reset, baseline planning and hidden truth.
- Reject non-JSON requests, non-object params, excessive request bodies and non-loopback Host/Origin headers.
- CSV exports decode correctly. Full replay information remains in JSON.

## Suggested first seven groups

Start with valid writes, atomic rejection, read-only heater, overpressure latch, conditional reset, seeded reproducibility and independent final replication. Separate deterministic physics/protocol assertions from statistical planner evaluation. A single random result cannot justify asserting that all seeds achieve error below 3 DN.
