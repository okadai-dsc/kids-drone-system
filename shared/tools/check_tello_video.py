"""Tello → このPC への映像(UDP 11111)受信を tellomon 抜きで単独テストする診断ツール。

前提:
  - tellomon を止めておく（8889 / 11111 を tellomon が握っていると bind 失敗する）
  - このPC が Tello の WiFi(192.168.10.x) に接続済み

実行:
  python check_tello_video.py

やること:
  1. Tello に command → streamon を送る（応答を表示）
  2. UDP 11111 を 10 秒待ち受けて、映像パケットが来るか/サイズ/本数を報告
  3. 最後に streamoff
"""

import socket
import time

TELLO = ("192.168.10.1", 8889)


def main():
    # --- コマンド用ソケット（ローカル 8889 で送受信）---
    cmd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        cmd.bind(("", 8889))
    except OSError as e:
        print(f"[NG] 8889 を bind できません: {e}")
        print("     → tellomon がまだ動いてませんか? 止めてから再実行してください。")
        return
    cmd.settimeout(5)

    def send(c):
        cmd.sendto(c.encode(), TELLO)
        try:
            r, _ = cmd.recvfrom(1024)
            return r.decode(errors="replace").strip()
        except TimeoutError:
            return "(無応答/timeout)"

    print(f"command  -> {send('command')}")
    print(f"streamon -> {send('streamon')}")

    # --- 映像受信ソケット（11111）---
    v = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        v.bind(("", 11111))
    except OSError as e:
        print(f"[NG] 11111 を bind できません: {e}")
        return
    v.settimeout(2)

    print("UDP 11111 を 10 秒間待ち受け中 ...")
    n = 0
    total = 0
    max_sz = 0
    over_mtu = 0  # 1472 byte 超のパケット数（WSL転送で落ちる閾値）
    first_sizes = []
    t0 = time.time()
    while time.time() - t0 < 10:
        try:
            d, _ = v.recvfrom(65535)
        except TimeoutError:
            continue
        n += 1
        total += len(d)
        max_sz = max(max_sz, len(d))
        if len(d) > 1472:
            over_mtu += 1
        if len(first_sizes) < 8:
            first_sizes.append(len(d))

    print("-" * 50)
    print(f"受信パケット数 : {n}")
    print(f"合計バイト     : {total}")
    print(f"最大パケット   : {max_sz} byte")
    print(f">1472B のパケット: {over_mtu} 個（WSL転送だと落ちる閾値）")
    print(f"最初の数個のサイズ: {first_sizes}")
    print("-" * 50)
    if n == 0:
        print("=> ✗ Tello から映像が届いていない")
        print(
            "   原因候補: streamon が ok でない / Windows Firewall が UDP 11111 を inbound ブロック"
        )
    else:
        print(f"=> ✓ 映像は届いている（{n} パケット / 約 {total // 1024} KB）")
        if over_mtu:
            print(
                f"   ただし {over_mtu} 個が 1472B 超 → WSL 経由転送だと落ちる。Windows ネイティブ転送なら可"
            )

    send("streamoff")
    cmd.close()
    v.close()


if __name__ == "__main__":
    main()
