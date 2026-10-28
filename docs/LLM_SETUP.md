# Real LLM integration through MCP

An MCP server exposes tools; it is not itself a language model. This project provides a local stdio bridge. Your chosen MCP-capable LLM client manages its model account and credentials. No API key belongs in the simulator.

## Connect a client

First start the shared dashboard server:

```powershell
.\.venv\Scripts\python.exe -m mixsim serve
```

Set a target and seed in the dashboard and start a new session. Configure a client that supports local stdio MCP with the example in `configs/mcp-client.example.json`:

```json
{
  "mcpServers": {
    "mixsim": {
      "command": "C:/Users/34477/Desktop/intership/.venv/Scripts/python.exe",
      "args": ["-m", "mixsim", "mcp", "--url", "http://127.0.0.1:8765"]
    }
  }
}
```

Adjust the absolute interpreter path if the project moves. Clients store their settings in different locations; this project does not modify any global client settings. The client starts the bridge subprocess itself. Running `python -m mixsim mcp` manually waits for protocol input on stdin; it does not open a webpage or run a model automatically.

## Available capabilities

- `list_devices`: active channels, driver envelope, target RGB and objective.
- `read_reference`: operating references for pump, daq and camera, also exposed as `mixsim://reference/{device}` resources.
- `read_device`: rig, pump_a, pump_b, daq or camera. No hidden-truth tool exists.
- `set_flows`, `write_channel`, `advance_time`: low-level control through the shared driver envelope.
- `run_experiment`: execute caller-selected rates for a bounded duration, measure and stop. There is no optimizer inside this tool.
- `recommend_setting`, `finalize_campaign`: explicitly select a successful trial and independently repeat it.
- `stop_pumps`, `reset_interlock`: stop and conditionally reset.
- `color_campaign`: reusable experiment prompt.

These eleven tools connect to the session visible in the dashboard. Fault injection, new-session control and built-in baseline optimization are deliberately not exposed to the agent.

## Suggested model task

```text
Complete a SIMULATED color-matching campaign using only the MixSim MCP tools.

First list devices and read the pump, DAQ and camera references.
Get target_rgb from the device information.
Choose both pump rates yourself, maintaining total flow at 400 uL/min.
Use 60 s settling per trial and at most 12 exploration trials.
Use measured RGB error to improve the next setting; do not use diagnostic truth.
If an interlock occurs, stop and report it instead of retrying nonzero writes.
Select one successful trial with recommend_setting, then call finalize_campaign.
Report trial count, selected flows, best observed error, and independent delivered error.
Explicitly state that this was simulation, not hardware validation.
```

Keep the dashboard open to observe tool-driven trials. Exported JSON labels protocol sources in `audit.source`, such as mcp, ui or cli. This identifies the caller surface, not a verified model identity. Record client, model name/version, prompt and date separately.

## Validation boundary

First verify real protocol initialization, tool/resource discovery, resource reads and tool calls. Then use an actual LLM client to choose trial parameters autonomously, recommend a setting and complete the final replicate.

Protocol smoke checks, scripted tool calls and the built-in feedback demo do not establish real-model performance. Until a model client has completed a campaign, describe LLM integration as prepared, not benchmarked or validated end to end.
