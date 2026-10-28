"""MCP stdio bridge: all operations hit the SAME session visible in the dashboard."""

from urllib.parse import urlsplit
from .cli import remote_action


def create_server(url="http://127.0.0.1:8765"):
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError('Install optional MCP dependencies: pip install -e ".[mcp]"') from exc
    parts = urlsplit(url)
    if parts.scheme != "http" or parts.hostname not in ("127.0.0.1", "localhost") or parts.username or parts.password:
        raise ValueError("MCP bridge requires an http loopback URL")
    mcp = FastMCP("MixSim virtual water and dye bench", instructions=(
        "Simulation only. Read device references before operating. You choose flow rates; do not call a hidden optimizer. "
        "Use experiment for a bounded trial (it stops both pumps). Observe RGB error and pressure. "
        "Recommend a successful record, then finalize once for independent delivered performance. "
        "Never claim hardware validation or LLM benchmark results from simulation."))

    def call(action, **params):
        return remote_action(url, action, params, "mcp")

    @mcp.tool()
    def list_devices() -> dict:
        """Get device channels, enforced limits, target RGB and objective."""
        return call("devices")

    @mcp.tool()
    def read_reference(device: str) -> dict:
        """Read operating knowledge for pump, daq or camera."""
        return call("reference", device=device)

    @mcp.resource("mixsim://reference/{device}")
    def device_reference(device: str) -> str:
        result = call("reference", device=device)
        if not result["ok"]:
            raise ValueError(result["error"]["message"])
        return result["result"]["text"]

    @mcp.resource("mixsim://reference/pump")
    def pump_reference() -> str:
        """Pump channels, units, command limits and stopping behavior."""
        return device_reference("pump")

    @mcp.resource("mixsim://reference/daq")
    def daq_reference() -> str:
        """Read-only voltage-derived sensors and pressure interlock."""
        return device_reference("daq")

    @mcp.resource("mixsim://reference/camera")
    def camera_reference() -> str:
        """Synthetic camera measurements, objective and replication."""
        return device_reference("camera")

    @mcp.tool()
    def read_device(device: str = "rig") -> dict:
        """Read rig, pump_a, pump_b, daq or camera. Camera read takes fresh noisy frames."""
        return call("read", device=device)

    @mcp.tool()
    def set_flows(a_ul_min: float, b_ul_min: float) -> dict:
        """Atomically write both pump flows in uL/min, through the driver envelope."""
        return call("set_flows", a_ul_min=a_ul_min, b_ul_min=b_ul_min)

    @mcp.tool()
    def write_channel(device: str, channel: str, value: float) -> dict:
        """Write a pump flow channel. DAQ/heater writes are always rejected."""
        return call("write", device=device, channel=channel, value=value)

    @mcp.tool()
    def advance_time(seconds: float) -> dict:
        """Advance virtual time by (0,600] seconds; interlock runs each integration step."""
        return call("advance", seconds=seconds)

    @mcp.tool()
    def run_experiment(a_ul_min: float, b_ul_min: float, settle_s: float = 60, label: str = "LLM trial") -> dict:
        """Run caller-selected flow rates for 1..600 s, measure camera and stop. No optimizer inside."""
        return call("experiment", a_ul_min=a_ul_min, b_ul_min=b_ul_min, settle_s=settle_s, label=label)

    @mcp.tool()
    def recommend_setting(record_id: int) -> dict:
        """Select one successful trial to independently replicate."""
        return call("recommend", record_id=record_id)

    @mcp.tool()
    def finalize_campaign() -> dict:
        """Rerun the recommendation once with fresh camera noise. Report this delivered result."""
        return call("finalize")

    @mcp.tool()
    def stop_pumps() -> dict:
        """Immediately stop both virtual pumps."""
        return call("stop")

    @mcp.tool()
    def reset_interlock() -> dict:
        """Reset only with stopped pumps, low pressure and no injected fault."""
        return call("reset_interlock")

    @mcp.prompt()
    def color_campaign() -> str:
        return ("Run a SIMULATED color matching campaign through these MCP tools only. First list devices and read "
                "the pump, DAQ and camera references. Get the target RGB. Choose your own pump rates with total "
                "400 uL/min; use 60 s per trial. Use only measured data to improve RGB RMSE, with at most 12 trials. "
                "Stop on any interlock and report the problem. Select a successful record using recommend_setting, "
                "then call finalize_campaign once. Report all trial count, chosen flows, best observed error, "
                "and independent delivered error separately. State that this is simulation, not bench validation.")

    return mcp


def run(url="http://127.0.0.1:8765"):
    create_server(url).run(transport="stdio")
