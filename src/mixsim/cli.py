import argparse
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import RigConfig
from .service import LabService, save_run


def remote_action(url, action, params=None, source="cli"):
    payload = json.dumps({"action": action, "params": params or {}, "source": source}, allow_nan=False).encode()
    request = Request(url.rstrip("/") + "/api/action", data=payload, headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=90) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser(description="MixSim — simulated water/dye bench")
    sub = parser.add_subparsers(dest="command", required=True)
    web = sub.add_parser("serve", help="Start the local dashboard and shared API")
    web.add_argument("--port", type=int, default=8765)
    web.add_argument("--config")
    demo = sub.add_parser("demo", help="Run a baseline campaign offline and save JSON")
    demo.add_argument("--planner", choices=["feedback", "random"], default="feedback")
    demo.add_argument("--seed", type=int, default=42)
    demo.add_argument("--target", type=float, default=0.68)
    demo.add_argument("--trials", type=int, default=10)
    demo.add_argument("--config")
    demo.add_argument("--output", default="runs/demo.json")
    call = sub.add_parser("call", help="Call the running server, e.g. call set_flows --params '{...}'")
    call.add_argument("action")
    call.add_argument("--params", default="{}")
    call.add_argument("--url", default="http://127.0.0.1:8765")
    mcp = sub.add_parser("mcp", help="Start stdio MCP bridge to the running dashboard")
    mcp.add_argument("--url", default="http://127.0.0.1:8765")
    args = parser.parse_args()
    try:
        if args.command == "serve":
            from .web import serve
            serve(args.port, RigConfig.load(args.config) if args.config else None)
        elif args.command == "mcp":
            from .mcp_server import run
            run(args.url)
        elif args.command == "call":
            params = json.loads(args.params)
            if not isinstance(params, dict):
                parser.error("--params must be a JSON object")
            result = remote_action(args.url, args.action, params)
            print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
            return 0 if result["ok"] else 2
        elif args.command == "demo":
            if not 1 <= args.trials <= 100:
                parser.error("--trials must be in [1, 100]")
            service = LabService(RigConfig.load(args.config) if args.config else None, args.seed, args.target)
            for _ in range(args.trials):
                response = service.dispatch("baseline_step", {"planner": args.planner}, "baseline")
                if not response["ok"] or response["result"]["status"] != "ok":
                    raise ValueError(f"Campaign aborted: {response}")
            best = min(service.records, key=lambda r: r["error_rgb_dn"])
            service.dispatch("recommend", {"record_id": best["id"]}, "baseline")
            response = service.dispatch("finalize", source="baseline")
            save_run(service, args.output)
            if not response["ok"] or response["result"]["status"] != "ok":
                raise ValueError(f"Final replicate failed: {response}")
            final = response["result"]
            print(json.dumps({"planner": args.planner, "trials": args.trials, "seed": args.seed,
                              "best_observed_error_rgb_dn": best["error_rgb_dn"],
                              "delivered_error_rgb_dn": final["error_rgb_dn"], "output": args.output}, indent=2))
    except (ValueError, RuntimeError, OSError, HTTPError, URLError) as exc:
        print(f"MixSim: {exc}", file=sys.stderr)
        return 2
    return 0
