"""operator_pc.emergency の純粋ロジックのテスト（#28 / 検収 F14・A2・P2）。"""

from __future__ import annotations

import time

from operator_pc.emergency import emergency_all, emergency_endpoints, send_all


def test_endpoints_for_four_pis():
    eps = emergency_endpoints({1: "192.168.0.11", 2: "192.168.0.12"}, 8001)
    assert eps == [
        "http://192.168.0.11:8001/emergency",
        "http://192.168.0.12:8001/emergency",
    ]


def test_default_endpoints_use_shared_ports():
    from shared.ports import PI_IPS, SCRATCH_HTTP_PORT

    eps = emergency_endpoints()
    assert len(eps) == len(PI_IPS)
    assert all(ep.endswith(f":{SCRATCH_HTTP_PORT}/emergency") for ep in eps)


def test_send_all_calls_poster_for_every_endpoint():
    called = []
    eps = [f"http://10.0.0.{i}:8001/emergency" for i in range(4)]
    res = send_all(eps, poster=lambda url: called.append(url))
    assert set(called) == set(eps)
    assert all(res[ep] for ep in eps)


def test_send_all_marks_failures():
    def poster(url):
        if "fail" in url:
            raise OSError("boom")

    eps = ["http://ok:8001/emergency", "http://fail:8001/emergency"]
    res = send_all(eps, poster=poster)
    assert res["http://ok:8001/emergency"] is True
    assert res["http://fail:8001/emergency"] is False


def test_send_all_runs_in_parallel_within_one_second():
    # 各 0.3s かかる poster を 4 本。直列なら 1.2s、並列なら 1s 未満（P2）。
    eps = [f"http://10.0.0.{i}:8001/emergency" for i in range(4)]
    start = time.monotonic()
    send_all(eps, poster=lambda url: time.sleep(0.3))
    assert time.monotonic() - start < 1.0


def test_emergency_all_combines_endpoints_and_send():
    called = []
    res = emergency_all({1: "192.168.0.11"}, 8001, poster=lambda url: called.append(url))
    assert called == ["http://192.168.0.11:8001/emergency"]
    assert res == {"http://192.168.0.11:8001/emergency": True}
