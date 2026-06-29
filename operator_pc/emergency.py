"""全機緊急停止: 各 Pi の tellomon へ emergency を並列送信する（#28 / 検収 F14・A2・P2）。

緊急停止は Tello 組込みの emergency（モータ即停止）を使用する（ユーザ確定方針）。
tellomon の REST は do_GET 実装のため、ここでは GET `http://<pi>:8001/emergency` を叩く
（設計書 5.4.5 は POST 表記だが、現行 tellomon の実装に合わせる）。

エンドポイント生成と並列送信は純粋ロジックとして切り出し、`poster` を注入してテストする。
本番は urllib による HTTP GET。押下から 1 秒以内に全機へ到達させるため並列実行する（P2）。
"""

from __future__ import annotations

import concurrent.futures
import urllib.request
from collections.abc import Callable, Mapping

from shared.ports import PI_IPS, SCRATCH_HTTP_PORT


def emergency_endpoints(
    pi_ips: Mapping[int, str] = PI_IPS, port: int = SCRATCH_HTTP_PORT
) -> list[str]:
    """各 Pi の緊急停止エンドポイント URL を返す。"""
    return [f"http://{ip}:{port}/emergency" for ip in pi_ips.values()]


def _http_get(url: str, timeout: float = 1.0) -> int:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.status


def send_all(
    endpoints: list[str],
    poster: Callable[[str], object] = _http_get,
    timeout: float = 1.0,
) -> dict[str, bool]:
    """各エンドポイントへ poster を並列実行し、URL→成否 の dict を返す。

    poster が例外を投げた URL は False。全機へ並列に送るため、1 台が遅くても
    他機の送信を待たせない（押下から 1 秒以内の到達を狙う / P2）。
    """
    if not endpoints:
        return {}
    results: dict[str, bool] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(endpoints)) as ex:
        future_to_url = {ex.submit(poster, url): url for url in endpoints}
        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            try:
                future.result()
                results[url] = True
            except Exception:
                results[url] = False
    return results


def emergency_all(
    pi_ips: Mapping[int, str] = PI_IPS,
    port: int = SCRATCH_HTTP_PORT,
    poster: Callable[[str], object] = _http_get,
) -> dict[str, bool]:
    """全 Pi へ緊急停止を並列送信する（エンドポイント生成＋送信のまとめ）。"""
    return send_all(emergency_endpoints(pi_ips, port), poster=poster)
