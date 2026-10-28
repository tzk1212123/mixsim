"""Six introductory flow tests. Run: python -m pytest -v."""

import pytest
from mixsim.rig import Rig, RigError


def test_valid_flow():
    rig = Rig()

    rig.set_flows(200,200)
    assert rig.commanded == [200, 200]

    rig.set_flows(100,300)
    assert rig.commanded == [100, 300]

    rig.set_flows(300, 100)
    assert rig.commanded == [300, 100]


def test_zero_flow():
    rig = Rig()

    rig.set_flows(0,200)
    assert rig.commanded == [0, 200]

    rig.set_flows(200,0)
    assert rig.commanded == [200, 0]

    rig.set_flows(0, 0)
    assert rig.commanded == [0, 0]


def test_negative_flow():
    rig = Rig()
    rig.set_flows(200, 200)

    with pytest.raises(RigError) as exc:
        rig.set_flows(-1, 200)
    assert exc.value.code == "flow_limit"
    assert rig.commanded == [200, 200]

    with pytest.raises(RigError) as exc:
        rig.set_flows(200, -1)
    assert exc.value.code == "flow_limit"
    assert rig.commanded == [200, 200]

    with pytest.raises(RigError) as exc:
        rig.set_flows(-1, -1)
    assert exc.value.code == "flow_limit"
    assert rig.commanded == [200, 200]


def test_per_pump_limit():
    rig = Rig()

    rig.set_flows(999, 0)
    assert rig.commanded == [999, 0]
    rig.set_flows(1000, 0)
    assert rig.commanded == [1000, 0]

    with pytest.raises(RigError) as exc:
        rig.set_flows(1001, 0)
    assert exc.value.code == "flow_limit"
    assert rig.commanded == [1000, 0]

    rig.set_flows(0, 999)
    assert rig.commanded == [0, 999]
    rig.set_flows(0, 1000)
    assert rig.commanded == [0, 1000]

    with pytest.raises(RigError) as exc:
        rig.set_flows(0, 1001)
    assert exc.value.code == "flow_limit"
    assert rig.commanded == [0, 1000]


def test_total_flow_limit():
    rig = Rig()

    rig.set_flows(750, 749)
    assert rig.commanded == [750, 749]
    rig.set_flows(750, 750)
    assert rig.commanded == [750, 750]

    with pytest.raises(RigError) as exc:
        rig.set_flows(750, 751)
    assert exc.value.code == "total_flow_limit"
    assert rig.commanded == [750, 750]


def test_invalid_type():
    rig = Rig()
    rig.set_flows(200, 200)

    # Each invalid value is checked on both pumps.
    for value in ("200", None, True, False, [], {}, float("nan"), float("inf"), -float("inf")):
        with pytest.raises(RigError) as exc:
            rig.set_flows(value, 200)
        assert exc.value.code == "invalid_number"
        assert rig.commanded == [200, 200]

        with pytest.raises(RigError) as exc:
            rig.set_flows(200, value)
        assert exc.value.code == "invalid_number"
        assert rig.commanded == [200, 200]
