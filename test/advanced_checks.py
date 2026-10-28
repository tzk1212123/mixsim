"""Simulator regression tests. Run from the project root: python -m pytest -v."""

import json
import math
import threading
from dataclasses import replace
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from mixsim.rig import Rig, RigError
from mixsim.config import RigConfig
from mixsim.physics import pressure_kpa, color_error
from mixsim.service import LabService, save_run
from mixsim.web import make_server
import pytest


# Optional advanced checks; excluded from default pytest discovery.

# NE-1000 manual section 12.7: device specifications, not project limits.
@pytest.mark.parametrize("profile,diameter,minimum,maximum", [
    ("hsw_norm_ject_10ml", 15.9, 0.13915, 607600 / 60),
    ("bd_10ml", 14.43, 0.1146, 8340),
])
def test_syringe_specification(profile, diameter, minimum, maximum):
    config = RigConfig(syringe_profile=profile)
    assert config.syringe.inside_diameter_mm == diameter
    assert config.syringe.min_flow_ul_min == pytest.approx(minimum)
    assert config.syringe.max_flow_ul_min == pytest.approx(maximum)
    rig = Rig(config)
    rig.set_flows(minimum, 0)
    assert rig.commanded == [minimum, 0]
    with pytest.raises(RigError) as exc:
        rig.set_flows(math.nextafter(minimum, 0), 0)
    assert exc.value.code == "flow_minimum"
    assert rig.commanded == [minimum, 0]
    with pytest.raises(RigError) as exc:
        rig.set_flows(maximum + 1, 0)
    assert exc.value.code == "device_flow_limit"
    assert rig.commanded == [minimum, 0]


def test_profile_changes_minimum_flow():
    bd = Rig(RigConfig(syringe_profile="bd_10ml"))
    bd.set_flows(0.12, 0)
    assert bd.commanded == [0.12, 0]
    with pytest.raises(RigError) as exc:
        Rig().set_flows(0.12, 0)
    assert exc.value.code == "flow_minimum"


@pytest.mark.parametrize("settings", [
    {"syringe_profile": "unknown"}, {"syringe_capacity_ul": 10001},
    {"syringe_capacity_ul": 0}, {"max_flow_ul_min": 11000},
    {"max_total_flow_ul_min": 2001}, {"max_total_flow_ul_min": 0.01},
    {"pressure_reset_kpa": 60}, {"camera_noise_rgb": -1},
    {"integration_step_s": 0}, {"camera_replicates": True},
    {"viscosity_pa_s": float("nan")},
])
def test_invalid_config(settings):
    with pytest.raises(ValueError):
        RigConfig(**settings)


@pytest.mark.parametrize("filename", ["configs/default.json", "configs/bd-10ml.json"])
def test_config_round_trip(filename, tmp_path):
    config = RigConfig.load(Path(__file__).resolve().parents[1] / filename)
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config.to_dict()), encoding="utf-8")
    assert RigConfig.load(path) == config


@pytest.mark.parametrize("seed", [-1, 2**32, True, 1.5, "42"])
def test_invalid_seed(seed):
    with pytest.raises(RigError) as exc:
        Rig(seed=seed)
    assert exc.value.code == "invalid_seed"


@pytest.mark.parametrize("channel", ["heater", "temperature_c", "pressure_kpa"])
def test_read_only_channels(channel):
    with pytest.raises(RigError) as exc:
        Rig().write_channel("daq", channel, 10)
    assert exc.value.code == "read_only"


def test_single_channel_write_enforces_combined_limit():
    rig = Rig()
    rig.set_flows(750, 750)
    with pytest.raises(RigError) as exc:
        rig.write_channel("pump_a", "flow_ul_min", 751)
    assert exc.value.code == "total_flow_limit"
    assert rig.commanded == [750, 750]


@pytest.mark.parametrize("seconds,code", [
    (0, "duration_limit"), (-1, "duration_limit"), (601, "duration_limit"),
    (float("nan"), "invalid_number"), (True, "invalid_number"),
])
def test_invalid_advance_preserves_state(seconds, code):
    rig = Rig()
    before = rig.snapshot()
    with pytest.raises(RigError) as exc:
        rig.advance(seconds)
    assert exc.value.code == code
    assert rig.snapshot() == before


def test_stop_and_explicit_time():
    rig = Rig()
    rig.set_flows(200, 200)
    assert rig.time_s == 0
    rig.advance(2)
    assert rig.time_s == pytest.approx(2)
    assert all(rate > 0 for rate in rig.actual)
    rig.stop()
    assert rig.commanded == rig.actual == [0, 0]
    remaining = rig.remaining.copy()
    mixture = rig.display_truth()["fraction_a"]
    rig.advance(2)
    assert rig.remaining == remaining
    assert rig.display_truth()["fraction_a"] == mixture


def test_overpressure_and_safe_recovery():
    rig = Rig(RigConfig(pressure_noise_kpa=0, calibration_sd=0))
    rig.set_clog(6)
    rig.set_flows(200, 200)
    for _ in range(100):
        rig.advance(0.1)
        if rig.interlock:
            break
    assert rig.interlock == "overpressure"
    assert rig.commanded == rig.actual == [0, 0]
    assert any(e["kind"] == "interlock" and e["reason"] == "overpressure" for e in rig.events)
    with pytest.raises(RigError) as exc:
        rig.set_flows(200, 200)
    assert exc.value.code == "interlock_latched"
    rig.set_flows(0, 0)
    with pytest.raises(RigError) as exc:
        rig.reset_interlock()
    assert exc.value.code == "reset_unsafe"
    rig.advance(5)
    with pytest.raises(RigError) as exc:
        rig.reset_interlock()
    assert exc.value.code == "fault_present"
    rig.set_clog(1)
    assert rig.interlock == "overpressure"
    rig.reset_interlock()
    assert rig.interlock is None
    rig.set_flows(200, 200)
    assert rig.commanded == [200, 200]


def test_empty_syringe_stops_both_pumps():
    rig = Rig(RigConfig(syringe_capacity_ul=1, calibration_sd=0))
    rig.set_flows(200, 0)
    rig.advance(10)
    assert rig.remaining == [0, 1]
    assert rig.interlock == "syringe_empty"
    assert rig.commanded == rig.actual == [0, 0]
    with pytest.raises(RigError) as exc:
        rig.reset_interlock()
    assert exc.value.code == "syringe_empty"


def test_seed_reproducibility_and_passive_polling():
    first, second = Rig(seed=7), Rig(seed=7)
    for rig in (first, second):
        rig.set_flows(300, 100)
        rig.advance(10)
    for _ in range(20):
        first.snapshot()
    assert first.camera() == second.camera()
    first.advance(1)
    second.advance(1)
    assert first.snapshot() == second.snapshot()
    assert first.camera() == second.camera()
    assert Rig(seed=7).camera() != Rig(seed=8).camera()


def test_daq_is_cached_but_camera_reads_are_fresh():
    lab = LabService()
    assert lab.read("daq") == lab.read("daq")
    assert lab.read("camera")["rgb"] != lab.read("camera")["rgb"]


def test_transport_delay_and_optical_steady_state():
    rig = Rig(RigConfig(calibration_sd=0, camera_noise_rgb=0, pressure_noise_kpa=0))
    initial = rig.camera()["rgb"]
    rig.set_flows(300, 100)
    rig.advance(1)
    assert rig.camera()["rgb"] == pytest.approx(initial)
    rig.advance(120)
    # Independently calculated optical densities for a 75% A mixture.
    expected = [245 * 10**(-od) for od in (0.4125, 0.4375, 1.07)]
    assert rig.camera()["rgb"] == pytest.approx(expected, abs=0.001)


def test_pressure_units_and_scaling():
    config = RigConfig()
    assert pressure_kpa(400, config) == pytest.approx(14.9225, abs=0.0001)
    assert pressure_kpa(800, config) == pytest.approx(2 * pressure_kpa(400, config))
    assert pressure_kpa(400, replace(config, tube_radius_m=0.0003)) == pytest.approx(pressure_kpa(400, config) / 16)
    assert pressure_kpa(400, config, 6) == pytest.approx(6 * pressure_kpa(400, config))
    assert color_error([3, 4, 0], [0, 0, 0]) == pytest.approx(math.sqrt(25 / 3))


def test_trial_and_independent_finalization():
    lab = LabService()
    trial = lab.experiment(200, 200, settle_s=2)
    assert trial["status"] == "ok"
    assert trial["kind"] == "trial"
    assert lab.rig.commanded == lab.rig.actual == [0, 0]
    lab.recommend(trial["id"])
    final = lab.finalize()
    assert final["id"] != trial["id"]
    assert final["kind"] == "replicate"
    assert final["recommended_from"] == trial["id"]
    assert final["started_s"] == trial["finished_s"]
    assert final["finished_s"] > trial["finished_s"]
    assert final["rgb"] != trial["rgb"]
    assert (final["a_ul_min"], final["b_ul_min"], final["settle_s"]) == (200, 200, 2)
    assert lab.final_record == final["id"]
    for action in (lab.finalize, lambda: lab.experiment(200, 200, 2)):
        with pytest.raises(RigError) as exc:
            action()
        assert exc.value.code == "campaign_complete"


def test_recommendation_required_and_invalidated_by_new_trial():
    lab = LabService()
    with pytest.raises(RigError) as exc:
        lab.finalize()
    assert exc.value.code == "recommendation_required"
    trial = lab.experiment(200, 200, 2)
    lab.recommend(trial["id"])
    lab.experiment(100, 300, 2)
    assert lab.recommendation is None


@pytest.mark.parametrize("record_id", [0, 99, True, 1.0, "1", None])
def test_invalid_recommendation(record_id):
    lab = LabService()
    lab.experiment(200, 200, 1)
    with pytest.raises(RigError) as exc:
        lab.recommend(record_id)
    assert exc.value.code == "invalid_record"


def test_aborted_trial_cannot_be_recommended():
    lab = LabService(RigConfig(pressure_noise_kpa=0, calibration_sd=0))
    lab.rig.set_clog(6)
    trial = lab.experiment(200, 200, 10)
    assert trial["status"] == "aborted"
    assert lab.rig.commanded == [0, 0]
    with pytest.raises(RigError) as exc:
        lab.recommend(trial["id"])
    assert exc.value.code == "invalid_record"


def test_aborted_final_replicate_does_not_complete_campaign():
    lab = LabService(RigConfig(pressure_noise_kpa=0, calibration_sd=0))
    trial = lab.experiment(200, 200, 10)
    lab.recommend(trial["id"])
    lab.rig.set_clog(6)
    assert lab.finalize()["status"] == "aborted"
    assert lab.final_record is None


def test_experiment_stops_even_if_camera_fails(monkeypatch):
    lab = LabService()
    def broken_camera():
        raise RuntimeError("Camera unavailable")
    monkeypatch.setattr(lab.rig, "camera", broken_camera)
    with pytest.raises(RuntimeError, match="Camera unavailable"):
        lab.experiment(200, 200, 1)
    assert lab.rig.commanded == lab.rig.actual == [0, 0]
    assert lab.records == []


def test_dispatch_errors_and_strict_json_export(tmp_path):
    lab = LabService()
    result = lab.dispatch("set_flows", {"a_ul_min": float("nan"), "b_ul_min": 200})
    assert result["ok"] is False
    assert result["error"]["code"] == "invalid_number"
    assert lab.dispatch("unknown")["error"]["code"] == "unknown_action"
    assert lab.dispatch("experiment", {"a_ul_min": 200, "b_ul_min": 200, "kind": "replicate"})["ok"] is False
    path = tmp_path / "run.json"
    save_run(lab, path)
    exported = json.loads(path.read_text(encoding="utf-8"))
    json.dumps(exported, allow_nan=False)
    assert exported["seed"] == 42
    assert exported["audit"][0]["ok"] is False
    assert exported["syringe_specification"] == lab.read("pump_a")["syringe"]


@pytest.mark.parametrize("a,b,settle,code", [
    (0, 0, 2, "zero_total_flow"), (200, 200, 0, "settle_range"),
    (200, 200, 601, "settle_range"), (200, 200, True, "invalid_number"),
])
def test_invalid_experiment(a, b, settle, code):
    lab = LabService()
    with pytest.raises(RigError) as exc:
        lab.experiment(a, b, settle)
    assert exc.value.code == code
    assert lab.records == []
    assert lab.rig.commanded == [0, 0]


def test_device_metadata_separates_capability_and_project_limits():
    lab = LabService()
    devices = lab.devices()
    assert devices["device_capability"]["max_per_pump_ul_min"] == pytest.approx(607600 / 60)
    assert devices["envelope"]["max_per_pump_ul_min"] == 1000
    assert devices["envelope"]["max_total_ul_min"] == 1500
    assert "hsw_norm_ject_10ml" in lab.reference("pump")["text"]
    assert lab.public_state()["syringe_specification"] == lab.read("pump_b")["syringe"]


@pytest.fixture
def http_lab():
    """Use a temporary port; never change the live dashboard session."""
    lab = LabService()
    server = make_server(port=0, service=lab)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    try:
        yield lab, f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_http_shares_state_and_driver_errors(http_lab):
    lab, url = http_lab

    def post(params):
        body = json.dumps({"action": "set_flows", "params": params}).encode()
        request = Request(url + "/api/action", data=body, headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=5) as response:
            return json.load(response)

    assert post({"a_ul_min": 200, "b_ul_min": 200})["ok"] is True
    assert lab.rig.commanded == [200, 200]
    assert post({"a_ul_min": -1, "b_ul_min": 200})["error"]["code"] == "flow_limit"
    with urlopen(url + "/api/state", timeout=5) as response:
        assert json.load(response)["rig"]["commanded_ul_min"] == [200, 200]


@pytest.mark.parametrize("body,content_type,status", [
    (b"not json", "application/json", 400),
    (b'{"action":"devices","params":[]}', "application/json", 400),
    (b'{"action":"devices"}', "text/plain", 415),
    (b'{"action":"set_flows","params":{"a_ul_min":NaN,"b_ul_min":0}}', "application/json", 400),
])
def test_http_rejects_malformed_requests(http_lab, body, content_type, status):
    lab, url = http_lab
    request = Request(url + "/api/action", data=body, headers={"Content-Type": content_type})
    with pytest.raises(HTTPError) as exc:
        urlopen(request, timeout=5)
    assert exc.value.code == status
    exc.value.close()
    assert lab.rig.commanded == [0, 0]


def test_http_rejects_external_origin(http_lab):
    _, url = http_lab
    request = Request(url + "/api/state", headers={"Origin": "https://example.com"})
    with pytest.raises(HTTPError) as exc:
        urlopen(request, timeout=5)
    assert exc.value.code == 403
    exc.value.close()
