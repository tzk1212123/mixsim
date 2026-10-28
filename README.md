# MixSim

A reproducible two-pump color-matching simulator for the semester hardware-control proposal. Two virtual syringe pumps feed a transport line and a mixing chamber. A synthetic camera measures color, and a controller adjusts the flows toward a target. Includes a local dashboard, Python API, CLI, and an actual MCP protocol bridge.

**No physical hardware is connected.** The pytest suite is in `test/test_rig.py`; see [the test plan](docs/TEST_PLAN.md) and [validation record](docs/VALIDATION.md).

## Start on this computer

The project `.venv` already contains the editable package and optional MCP dependencies. Double-click **Start-MixSim.cmd**, keep the terminal open, and visit **http://127.0.0.1:8765**.

Alternatively, in PowerShell from this directory:

```powershell
.\.venv\Scripts\python.exe -m mixsim serve
```

Use `--port 8766` if the default port is occupied. Only one server can bind a port. The server listens on loopback only; Ctrl+C stops it. Refreshing the dashboard preserves the current server session.

Manual controls and the safety/event log expand on demand.

## Try two demonstrations

1. Keep target recipe 68%, seed 42, total flow 400 uL/min, settling time 60 s, and 10 trials. Click **Run campaign**. The feedback baseline explores, selects a recommendation, and independently repeats it. Every observation and the final replicate remain visible. This controller is not an LLM.
2. Export JSON, then create a new session. Inject a x6 clog and run the default manual trial at 200/200 uL/min. Overpressure stops both pumps and latches the interlock. A nonzero flow write is then rejected. Clear the clog, advance 10 s for simulated pressure decay, and explicitly reset the interlock. Clearing a clog alone does not reset a latched fault.

Experiment time is virtual: 10 trials plus one final replicate at 60 s each represent 660 s of experiment time. Wall-clock pauses only make the dashboard demonstration easier to follow. Setting flow alone does not move fluid; explicitly advance time or run an experiment.

The target slider generates a target RGB from a **nominal recipe**. It is not the true optimal command ratio: the pumps have seed-dependent calibration bias. Controllers use measured color to optimize. Target and seed changes apply only when starting a new session.

## Install on another computer

Requires Python 3.11+. The simulator and dashboard use the standard library; MCP is optional.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[mcp]"
.\.venv\Scripts\python.exe -m mixsim serve
```

Install and run the pytest suite:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev,mcp]"
.\.venv\Scripts\python.exe -m pytest
```

Pytest discovers `test/` automatically. Add `-v` to show each case. Tests create their own simulators and do not require the dashboard server. `requirements-lock.txt` records the earlier Windows installation; the portable dependency definition is `pyproject.toml`.

## Continuous integration

`.github/workflows/tests.yml` runs the six introductory tests on GitHub using Python 3.12. After pushing the project to a GitHub repository, open its **Actions** tab and select **Tests** to see the result. Pushes and pull requests trigger it automatically; **Run workflow** also starts it manually when the workflow is on the default branch. The configuration follows the official [checkout](https://github.com/actions/checkout) and [setup-python](https://github.com/actions/setup-python) examples. A local pytest pass does not establish a GitHub CI pass.

## Syringe profiles

The default is HSW Norm-Ject 10 mL (15.9 mm inside diameter). Both pumps share one selected profile. To use the manual's B-D 10 mL example (14.43 mm):

```powershell
.\.venv\Scripts\python.exe -m mixsim serve --config configs/bd-10ml.json
```

In Python, use `RigConfig(syringe_profile="bd_10ml")`. Manufacturer flow capability is separate from the assumed project limits of 1000 uL/min per pump and 1500 uL/min combined. `syringe_capacity_ul` sets initial fill, bounded by the selected syringe capacity. Device metadata and JSON exports include the resolved specification and manual source. See MODEL.md for limitations.

## Python and CLI

```python
from mixsim.service import LabService

lab = LabService(seed=42, target_fraction=0.68)
print(lab.dispatch("devices"))
print(lab.dispatch("experiment", {
    "a_ul_min": 272,
    "b_ul_min": 128,
    "settle_s": 60,
}))
print(lab.dispatch("recommend", {"record_id": 1}))
print(lab.dispatch("finalize"))
```

`LabService.dispatch` returns `{"ok": true, "result": ...}` or `{"ok": false, "error": {"code": ..., "message": ...}}`. Direct `Rig` methods raise `RigError`. All control surfaces use the same driver safety boundary. A new Python service object has its own session; CLI and MCP connect to the dashboard session by default.

Run a complete offline baseline without starting the dashboard:

```powershell
.\.venv\Scripts\python.exe -m mixsim demo --seed 42 --trials 10 --output runs\demo.json
.\.venv\Scripts\python.exe -m mixsim demo --planner random --seed 42 --output runs\random.json
```

Call the running dashboard server:

```powershell
.\.venv\Scripts\python.exe -m mixsim call devices
.\.venv\Scripts\python.exe -m mixsim call set_flows --params '{"a_ul_min":200,"b_ul_min":200}'
.\.venv\Scripts\python.exe -m mixsim call advance --params '{"seconds":10}'
.\.venv\Scripts\python.exe -m mixsim call stop
```

These quoting examples assume PowerShell 7. Windows PowerShell 5.1 can handle native-command JSON quoting differently; use the Python API or dashboard if needed.

## Real LLM integration

See [LLM setup](docs/LLM_SETUP.md). The stdio MCP bridge exposes three device references, eleven tools, and a campaign prompt. It connects to the same HTTP server, so actual model tool calls appear in the dashboard.

**Protocol connectivity and real-model validation are separate.** No model credentials are included or configured. Connecting a real LLM client is still required before claiming a model-driven campaign. The built-in feedback controller is clearly labeled as a baseline.

## Scope and limitations

- [Model documentation](docs/MODEL.md) provides equations, units, authoritative sources, assumptions, and limitations.
- [Demonstration guide](docs/DEMO.md) provides a sequence to accompany a PowerPoint talk. No slide deck has been generated.
- [Pytest plan](docs/TEST_PLAN.md) describes covered behaviors and further testing opportunities.
- Manufacturer data informs example pump ranges and DAQ resolution. Geometry, project safety thresholds, response dynamics, noise, and dye optics remain configurable assumptions requiring bench calibration.
- This is an MHS-style interface, not a claim of compliance with an unavailable official MHS driver API.
- Real NE-1000 serial, NI-DAQmx and OpenCV drivers are not implemented. `DeviceBackend` sketches the future adapter contract.
- The proposal's earlier yield/heater/BO/OFAT benchmark and its reported 1,050 campaigns are not reproduced. The optional summer droplet task is outside this implementation.
- Sessions are in memory. Export before creating a new session or closing the server. JSON contains full configuration, seed, audit and event data; CSV contains experiment records only.
- Reproducibility requires the same seed, configuration and explicit operation sequence. Extra camera reads draw extra noise samples; passive dashboard polling does not.

## Project structure

```text
src/mixsim/config.py        Configuration and validation
src/mixsim/syringes.py      Manual-sourced syringe profiles
src/mixsim/physics.py       Flow resistance and optical equations
src/mixsim/rig.py           Virtual devices, time integration, safety envelope
src/mixsim/service.py       Trials, recommendations, final replication, dispatch
src/mixsim/cli.py           CLI and offline baseline demo
src/mixsim/web.py           Loopback HTTP server
src/mixsim/mcp_server.py    Stdio MCP bridge
src/mixsim/references/      Natural-language device operating references
src/mixsim/static/          Local dashboard; no CDN or frontend build required
configs/default.json       Default model configuration
configs/mcp-client.example.json  Example MCP client configuration
```
