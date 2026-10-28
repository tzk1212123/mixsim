# Implementation smoke-check record

## Automated regression suite (October 28, 2026)

The default suite was subsequently simplified at the student's request to six
introductory test functions in `test/test_rig.py`. Advanced cases are preserved
in `test/advanced_checks.py`, excluded from default discovery. The 92-case result
below records the earlier combined suite, not the current default test count.

Command: `.\.venv\Scripts\python.exe -m pytest -q`.
Result: **92 passed** on Windows, in 0.54 seconds on this run.
At the time of that run all cases were in `test/test_rig.py`.
Coverage includes the six initial flow-input groups, manual-sourced syringe
boundaries, invalid configurations, atomic rejection, read-only channels,
overpressure and recovery, depletion, reproducibility, transport/optics,
pressure units/scaling, trial/final-replicate integrity, strict JSON exports,
and isolated HTTP requests. HTTP tests use temporary ports and independent sessions.

The suite exposed a floating-point conversion defect: the B-D minimum command
`0.1146 uL/min` was rejected because binary division of `6.876 / 60` rounded
above that value. Decimal conversion now preserves the manual-derived boundary;
the immediately lower representable float is still rejected.
These tests verify simulated behavior, not bench accuracy or real-LLM performance.

## Syringe-profile correction (model 0.1.1)

The supplied NE-1000 manual now defines two explicit profiles: HSW Norm-Ject
10 mL / 15.9 mm and B-D 10 mL / 14.43 mm. Manual/scripted checks confirmed
their converted flow boundaries, acceptance of 0.12 uL/min only for B-D,
atomic rejection, invalid-profile/initial-fill validation, configuration JSON
round-trips, and agreement between device metadata, active references and exports.
The default ten-trial campaign plus final replication completed with delivered
RGB RMSE approximately 0.3151 DN. The live server and actual MCP reference/device
calls were checked after restarting with the default profile. The student's
pytest file was not modified and pytest was not run.

The earlier checks below were manual/scripted smoke checks with Python 3.12 on Windows, not a statistical benchmark. At that stage pytest was still student-owned; the automated suite above was added later at the student's request.

## Checks completed

- Python source compilation and JavaScript syntax check.
- A complete browser-operated feedback campaign: ten exploration trials and one independent final replicate, visible in the same dashboard session.
- Negative flow, combined-flow overflow, nonfinite Python input and read-only heater rejection. Invalid atomic writes left both previous commands unchanged.
- Sixfold clog resistance caused overpressure, stopped both pumps and latched the interlock. Nonzero restart and premature reset failed. Clearing the fault, advancing time and explicitly resetting restored operation.
- Strict JSON export remained valid after rejecting a Python NaN input.
- Passive dashboard state polling did not change a seeded experiment trajectory.
- Three standalone seeded feedback campaigns completed with final replication and retained logs.
- Actual MCP stdio initialization, discovery of eleven tools and three static reference resources, reference reads, rejected invalid command, three scripted experiments, recommendation and final replication.
- MCP-origin actions appeared in the same dashboard session and exported audit. Tools did not expose built-in optimization, fault injection or diagnostic truth.
- CSV and JSON export, malformed requests, invalid Origin, nonfinite JSON rejection and CLI failure exit code.
- Source, interface and project documentation were checked for remaining Chinese text; all project-facing content is English. The original supplied proposal was preserved.

## Example outcomes

Default target recipe is nominal A fraction 0.68. Total flow is 400 uL/min, settling time 60 s, and the feedback baseline uses ten exploration trials.

| Seed | Independent delivered RGB RMSE, DN |
|---|---:|
| 0 | 0.1988 |
| 7 | 0.1722 |
| 42 | 0.3151 |

These three smoke-check outcomes do not establish general planner performance. The scripted MCP protocol check used three preselected trials and produced a final error of approximately 0.8284 DN. It was **not an LLM-controlled campaign**.

Local evidence is saved under `runs/`: feedback-seed-0.json, feedback-seed-7.json, feedback-seed-42.json, fault-demo.json, browser-demo.json and mcp-protocol-smoke.json. These generated files are ignored by version control. Full assumptions and source citations are in MODEL.md.

## Not yet validated

- Cross-platform execution, complete interface coverage and automated MCP protocol regression tests.
- Autonomous parameter selection by a real LLM client. MCP is prepared and protocol-checked; no model account or credentials were configured.
- Physical pumps, transducers, camera, actual dye spectra, tubing/chip geometry, real emergency-stop behavior or sim-to-real error.
- The proposal's earlier yield/heater/BO/OFAT benchmark and optional droplet task.
