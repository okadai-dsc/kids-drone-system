import socket
import json
from datetime import datetime
import time
import sys
import os

# 親ディレクトリの shared をインポートできるようにパスを追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from shared.schemas import YoloResult, Detection

def run_sender():
    host = "127.0.0.1"
    port = 11112

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # 1. テキスト "hello" を1回送る
    print("Sending 'hello'...")
    sock.sendto(b"hello", (host, port))
    
    time.sleep(1)

    # 2. shared/schemas.py の検知結果 JSON 形式の文字列を送る
    result = YoloResult(
        tello_id="Tello#1",
        ts=datetime.now().isoformat(timespec="milliseconds"),
        detections=[
            Detection(label="cat", confidence=0.95, bbox=[100, 100, 200, 200])
        ],
        image_b64="<dummy_base64_string>"
    )
    
    json_data = result.to_json()
    print(f"Sending JSON data: {json_data}")
    sock.sendto(json_data.encode("utf-8"), (host, port))
    
    sock.close()
    print("Done.")

if __name__ == "__main__":
    run_sender()
