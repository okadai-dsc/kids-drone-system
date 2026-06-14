import socket
import json

def run_receiver():
    # UDPポート 11112 で待機
    host = "0.0.0.0"
    port = 11112

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((host, port))
    print(f"Listening on udp://{host}:{port}")

    try:
        while True:
            data, addr = sock.recvfrom(65536)
            print(f"\nReceived {len(data)} bytes from {addr}")
            
            try:
                # JSONとしてパースを試みる
                text = data.decode("utf-8")
                parsed = json.loads(text)
                print(f"Parsed JSON dict: {parsed}")
            except (UnicodeDecodeError, json.JSONDecodeError):
                # JSONでなければそのまま bytes として表示
                print(f"Raw bytes: {data}")
    except KeyboardInterrupt:
        print("\nReceiver stopped.")
    finally:
        sock.close()

if __name__ == "__main__":
    run_receiver()
