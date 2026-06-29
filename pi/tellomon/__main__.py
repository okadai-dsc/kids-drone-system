import argparse
import datetime
import math
import queue
import socket
import threading
import time
import tkinter as tk
import tkinter.filedialog
import tkinter.messagebox
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from tkinter import END, NW, VERTICAL, E, IntVar, N, StringVar

import cv2

from shared.ports import NOTE_PC_IP, PI_TO_YOLO_VIDEO_PORTS

from . import cage, commands
from . import safety
from .beacon import BeaconSender

# このモジュールが置かれているディレクトリ（gif アセットを実行場所に依らず開くため）
_HERE = Path(__file__).resolve().parent

"""
 Tello制御プログラム

 Tello SDKのインタフェースを利用してTelloの飛行を制御するプログラムです。
 Tello制御プログラムは、下記の3つのスレッドから構成されます。
 (1)メインスレッド
   Telloの飛行状況を表示します。
   a)飛行図面を表示して、Telloコマンドの実行結果従いTelloの想定位置と全面方向を飛行図面
   　に表示します。
     ・飛行図面は、「図面選択」ボタンを使用して変更できます。
     ・Telloの想定位置と全面方向はTelloへのコマンドに従い表示します。
     ・Telloの飛行開始位置と飛行開始時の向きは、飛行図面の下のボックスに設定して「リセット」
     　ボタンを押下することで変更できます。
   b)Telloのステータス情報に従い、高さ、スピード、バッテリ容量、飛行時間を画面に表示します。
   c)飛行図面は下記の通りです。
      サイズ：300×300ピクセル
      ファイル形式：GIF
   d)飛行図面は下記のサイズに対応させてください。
      室内：15m×15m
      屋外：300m×300m
　　　　飛行図面の原点は、変更可能です。

 (2)Webサーバスレッド
 　　httpのインタフェースでTelloコマンドを受け付け、Telloに送信します。
   Telloからの応答が「ok」の場合、HTTPステータスを200、それ以外は500で応答します。
   a)Telloコマンドは下記の形式です。
 　　　　パラメータが無い場合：　/コマンド
 　　　　パラメータが有る場合：　/コマンド/パラメータ
 　　　　[例]
 　　　　　　http://localhost:8001/forward/50

   b)telloの接続情報は下記の通りです。
 　   IPアドレス：192.168.10.1
     ポート：8889
   c)Webサーバの接続情報は下記の通りです。
 　   IPアドレス：localhost
     ポート：8001
   d)Telloコマンドと応答結果は、画面の「Telloコマンド：応答」に表示します。
 　　　　[例]
 　　　　　　/forward/50 : OK

 (3)ステート受信スレッド
 　　Telloから送信されるステートを受信し、ステートに含まれる速度、高さ、バッテリー
 　　の残容量、飛行時間を画面に表示します。
 　　また、Telloから送信されるステートを受信状況を画面に表示します。
   a)telloの接続情報は下記の通りです。
 　   IPアドレス：0.0.0.0
     ポート：8890
   b)ステートの受信状況は画面の「通信状態」に下記の通り表示します。
     緑　　：過去1秒以内にTelloからのステートを受信
     赤　　：1秒以上Telloからのステートを受信していない

(4)データ受け取り用のスレッドの実装関数
    run_udp_receiver():





"""

#
# 定数の定義
#
# ルートウィンドウのサイズとタイトル
WINDOW＿SIZE = "630x473"
WINDOW_TITLE = "ドローンコントロールプログラム(Ver 1.6) "

# キャンバスのサイズと背景色
CANVAS_WIDTH = 400  # 変更不可
CANVAS_HEIGHT = 350  # 変更不可
CANVAS_BG = "#C0C0C0"

# 飛行地図の基準座標
CANVAS_X_BASE = 50  # 変更不可
CANVAS_Y_BASE = 320  # 変更不可

# ドローンの基準座標
DRONE_X_BASE = 0  # 変更可能
DRONE_Y_BASE = 0  # 変更可能

# ドローンの飛行情報
DRONE_PIXEL = 5  # 1ピクセルを5cmとする 変更可能
DRONE_CAGE = 100  # ケージの位置(外枠からの長さ:cm)
DRONE_CAGE_P = 20  # ケージの位置(外枠からの長さ:ピクセル)

# ドローンの初期位置と方向
DRONE_X_POS = "0"  # 変更可能
DRONE_Y_POS = "0"  # 変更可能
DRONE_DIRECTION = "90"  # 変更可能

# ドローン接続情報
SERVER_ADDRESS = "192.168.10.1"
SERVER_PORT = 8889
serv_address = (SERVER_ADDRESS, SERVER_PORT)

MSG_SIZE = 1024

# ビデォ転送情報
VIDEO_FLAG = 0

# --- ケージ制御（#30 / 検収 F5・S2・S3）------------------------------
# 想定位置（メートル系。表示用キャンバスのレガシー座標とは別管理）を積算し、
# ケージ外/高度2m超になる移動コマンドを Tello に送らず抑止する。
CAGE_GUARD = True  # False で抑止を無効化（デバッグ/キャリブレーション用）
# 離陸時の想定位置(m)。既定はケージ中央。実機では離陸位置に合わせて調整する。
INIT_X = (cage.CAGE_X[0] + cage.CAGE_X[1]) / 2  # 3.25
INIT_Y = (cage.CAGE_Y[0] + cage.CAGE_Y[1]) / 2  # 1.75
INIT_YAW = 0
DRONE_STATE = cage.DroneState(x=INIT_X, y=INIT_Y, z=0.0, yaw=INIT_YAW)

SrcAddr = ("0.0.0.0", 8890)
SOCKET_TIMEOUT = 60  # 変更可能

#
# グローバル変数の情報
#
msg_queue = queue.Queue()  # Webメッセージキュー
err_queue = queue.Queue()  # Webメッセージキュー

# telloからの受信用
VS_UDP_IP = "0.0.0.0"
VS_UDP_PORT = 11111
VS_FLAG = 0
VS_IMG = 0
cap = None

thread1 = None

CAMERA = "0"


#
# データ受け取り用のスレッドの実装関数
#
def run_udp_receiver(drone_num):

    M_SIZE = 65535
    # 0.0.0.0 で待受（Tello網のDHCPで割り当てIPが 192.168.10.2 以外でも受信できるように）
    host = "0.0.0.0"
    port = 11111
    locaddr = (host, port)
    recv_sock = socket.socket(socket.AF_INET, type=socket.SOCK_DGRAM)
    # Telloからのビデオ受信ポートを生成する
    while True:
        try:
            print("recv_socket.bindの実行")
            recv_sock.bind(locaddr)
            break
        except OSError:
            # 失敗した場合は2秒待って再実行する。
            time.sleep(2)

    # モニタのアドレスとポートの定義
    serv1_address = ("127.0.0.1", 11112)
    send_sock1 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # 外部の転送先（YOLO PC）のアドレスとポート。shared.ports から機体番号で引く
    serv2_address = (NOTE_PC_IP, PI_TO_YOLO_VIDEO_PORTS[drone_num])
    # YOLO PC への転送ソケットは 1 本を使い回す（毎パケット作ると FD が枯渇し途中で止まる）
    send_sock2 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print(
        f"[video] receiver ready: recv {locaddr} -> monitor {serv1_address} / YOLO {serv2_address}"
    )

    rx_count = 0  # 直近 1 秒の Tello からの受信パケット数
    fwd_count = 0  # 直近 1 秒の YOLO PC への転送パケット数
    last_log = time.time()
    while True:
        try:
            message, cli_addr = recv_sock.recvfrom(M_SIZE)
        except OSError:
            recv_sock.bind(locaddr)
            time.sleep(2)
            continue

        rx_count += 1
        try:
            # モニタにビデオを転送する
            send_sock1.sendto(message, serv1_address)
            # 外部（YOLO PC）にビデオを転送する
            if VIDEO_FLAG == 1:
                send_sock2.sendto(message, serv2_address)
                fwd_count += 1

        except OSError:
            continue

        # 1 秒ごとに「Tello から受信／YOLO PC へ転送」した pkt/s を出す
        now = time.time()
        if now - last_log >= 1.0:
            print(
                f"[video] rx={rx_count}pkt/s  forwarded_to_yolo={fwd_count}pkt/s  "
                f"VIDEO_FLAG={VIDEO_FLAG}  -> {serv2_address[0]}:{serv2_address[1]}"
            )
            rx_count = 0
            fwd_count = 0
            last_log = now


# ビデオ画像のモニタ用関数
def run_udp_monitor():
    global cap
    global VS_FLAG
    global VS_IMG

    #    udp_video_address = 'udp://@192.168.0.20:11112'
    udp_video_address = "udp://@127.0.0.1:11112"
    if cap is None:
        cap = cv2.VideoCapture(udp_video_address)
        print("run_udp_monitor#VideoCapture")

    if not cap.isOpened():
        cap.open(udp_video_address)
        print("run_udp_monitor#open")

    while True:
        ret, frame = cap.read()
        if not ret:
            cv2.waitKey(2000)
            cap.release()
            cv2.destroyAllWindows()
            cap = cv2.VideoCapture(udp_video_address)
            cap.open(udp_video_address)
            print("run_udp_monitor#release -> open")
            continue

        width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        #       height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        #       print(width)
        #       print(height)

        if width == 320:
            # 下向きカメラの場合は、画像を回転させてサイズを変更する
            #            frame1 = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
            frame2 = cv2.resize(frame, dsize=(600, 450))
            frame2 = frame2
        else:
            # 前方カメラの場合はサイズを変更する。
            frame2 = cv2.resize(frame, dsize=(600, 450))
            frame2 = frame2

        cv2.imshow("Drone Video Screen", frame2)

        # イメージ出力の場合は、画像をディスクトップに書き出す。
        if VS_IMG == 1:
            print("run_udp_monitor#write")
            now = datetime.datetime.now()
            filename = "/home/pi/Desktop/drone" + now.strftime("%H%M%S") + ".png"
            cv2.imwrite(filename, frame)
            VS_IMG = 0

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cap = None
    cv2.destroyAllWindows()


# --- classes ---
class ComHandler:
    def __init__(self):
        self.local_ip = ""
        self.local_port = 8889
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.local_ip, self.local_port))
        print("ComHandler# __init__:")
        # ソケットのタイムアウト値を設定
        self.sock.settimeout(SOCKET_TIMEOUT)

    def send_cmd(self, message):
        # Telloにコマンドを送信する。
        print("send_cmd#Start,Command:" + message)
        try:
            self.sock.sendto(message.encode("utf-8"), serv_address)
            print("send_cmd#Waiting response")
            rx_meesage, addr = self.sock.recvfrom(MSG_SIZE)
            print("send_cmd#Receive Response,Message:" + rx_meesage.decode(encoding="utf-8"))

            if rx_meesage.decode(encoding="utf-8") != "ok":
                print("send_cmd#retry")
                for i in range(3):
                    time.sleep(2)
                    print(i)
                    self.sock.sendto(message.encode("utf-8"), serv_address)
                    print("send_cmd_retry#Waiting response")
                    rx_meesage, addr = self.sock.recvfrom(MSG_SIZE)
                    print(
                        "send_cmd_retry#Receive Response,Message:"
                        + rx_meesage.decode(encoding="utf-8")
                    )
                    if rx_meesage.decode(encoding="utf-8") == "ok":
                        break

            # レスポンス情報を返却(ok / error)
            return rx_meesage.decode(encoding="utf-8")

        except OSError as exc:  # change
            print(f"send_cmd#Caught exception socket.error : {exc}")
            # レスポンス情報を返却(timeout)
            return exc


# コマンド送信用ソケットの作成
com = ComHandler()


class StatusRecever:
    def __init__(self, view):
        # ステータス受信用ソケット作成
        self.udpServSock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # 受信側アドレスでソケットを設定
        self.udpServSock.bind(SrcAddr)
        self.view = view
        # ビーコン送信スレッドが参照する最新ステータス（tkinter 変数を跨いで読まないため）
        self.latest = {"height_cm": 0, "battery": 0, "flight_time": 0, "yaw": 0}

    def receve_forever(self):
        while True:
            data, addr = self.udpServSock.recvfrom(MSG_SIZE)
            # ステータス文字列のパースは safety.parse_tello_status に一元化（#29）。
            status = safety.parse_tello_status(data.decode(encoding="utf-8", errors="ignore"))
            self.view.koudo_var.set(status["height_cm"])
            self.view.dengen_var.set(status["battery"])
            self.view.hikouzikan_var.set(status["flight_time"])
            self.view.sokudo_var.set(status["speed_cm_s"])

            # ビーコン送信スレッド用に最新ステータスを保持
            self.latest = {
                "height_cm": status["height_cm"],
                "battery": status["battery"],
                "flight_time": status["flight_time"],
                "yaw": status["yaw"],
            }

            # status を受信したので通信健全カウンタをリセット
            Controller.HEALTH_COUNTER = 0


class HttpHandler(BaseHTTPRequestHandler):
    def do_GET(self):

        global VS_FLAG
        global VS_IMG
        global VIDEO_FLAG
        global thread1
        global thread2

        err_queue.put(f"{self.path}:")

        global DRONE_STATE

        print("do_GET#Start,message:" + self.path)
        message = self.path + "//"
        opcode = message.split("/")[1]
        param = message.split("/")[2]

        # ケージ制御（#30 / F5・S2・S3）: 想定位置でケージ外 or 高度2m超になる
        # 移動/上昇コマンドは Tello に送らず抑止する（cage.would_exceed は純粋ロジック）。
        if CAGE_GUARD and opcode in cage.CAGE_MOTION:
            try:
                _param_cm = int(param)
            except ValueError:
                _param_cm = 0
            if cage.would_exceed(DRONE_STATE, opcode, _param_cm):
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(bytes("OK(cage-blocked)", "utf-8"))
                msg_queue.put(f"ケージ抑止: {opcode} {param}")
                err_queue.put(f"{self.path}:cage-blocked")
                return

        # Telloにコマンドを送信する。送信文字列の組み立ては commands.build_command に一元化。
        # emergency（モータ即停止、検収 A1/A2）も takeoff/land と同列の SDK コマンド。
        if opcode == "streamwrite":
            # 画面キャプチャ指示（Tello へは送らないアプリ内コマンド）
            VS_IMG = 1
            trn_msg = "ok"
        else:
            cmd = commands.build_command(opcode, param)
            if cmd is None:
                return  # 未知 opcode
            trn_msg = com.send_cmd(cmd)
            if opcode == "takeoff":
                time.sleep(5)

        if trn_msg == "ok":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            #            self.wfile.write(bytes("<html><head><title>https://pythonbasics.org</title></head>", "utf-8"))
            #            self.wfile.write(bytes("<p>Request: %s</p>" % self.path, "utf-8"))
            #            self.wfile.write(bytes("<body>", "utf-8"))
            #            self.wfile.write(bytes("<p>This is an example web server.</p>", "utf-8"))
            #            self.wfile.write(bytes("</body></html>", "utf-8"))

            self.wfile.write(bytes("OK", "utf-8"))

            # ケージ制御（#30）: 送信成功したコマンドで想定位置を積算する。
            # takeoff で離陸位置にリセット、移動/回転/上下で dead-reckoning。
            if opcode == "takeoff":
                DRONE_STATE = cage.DroneState(x=INIT_X, y=INIT_Y, z=0.0, yaw=INIT_YAW)
            elif opcode in cage.CAGE_MOTION:
                try:
                    _param_cm = int(param)
                except ValueError:
                    _param_cm = 0
                DRONE_STATE = cage.apply_command(DRONE_STATE, opcode, _param_cm)

            if opcode == "streamon":
                VS_FLAG = 0
                VS_IMG = 0
                # 映像開始と同時に YOLO PC への転送も有効化する
                # （run_udp_receiver が VIDEO_FLAG==1 のとき serv2 へ転送する）
                VIDEO_FLAG = 1
                if thread1 is None:
                    thread1 = threading.Thread(target=run_udp_monitor, args=())
                    thread1.daemon = True
                    thread1.start()

            if opcode == "streamoff":
                VS_FLAG = 1
                # 映像停止に合わせて YOLO PC 転送も止める
                VIDEO_FLAG = 0

            # Telloコマンドが正常終了した場合、Telloの状態を変更する様に
            # メインスレッドにキューを使用して依頼
            msg_queue.put(f"{self.path}")
            err_queue.put(f"{self.path}:{trn_msg}")

        else:
            self.send_response(500)
            self.send_header("Content-type", "text/html")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(bytes(f"{trn_msg}", "utf-8"))

            err_queue.put(f"{self.path}:{trn_msg}")


class View:
    def __init__(self, app):

        self.master = app

        # 飛行図面の定義（モジュール同梱の gif を実行場所に依らず開く）
        self.gif_file = StringVar()
        self.gif_file.set(str(_HERE / "tellomon.gif"))
        self.gif_image = tk.PhotoImage(file=self.gif_file.get())
        # ドローンの図形の定義
        self.drone_file = str(_HERE / "drone.gif")
        self.drone_image = tk.PhotoImage(file=self.drone_file)
        # ドローンの初期位置と方向の定義
        self.drone_x_pos = StringVar()
        self.drone_x_pos.set(DRONE_X_POS)
        self.drone_y_pos = StringVar()
        self.drone_y_pos.set(DRONE_Y_POS)
        self.drone_direction = StringVar()
        self.drone_direction.set(DRONE_DIRECTION)
        # 現在のドローンの位置と方向を管理する変数
        self.x_addr = CANVAS_X_BASE + int(self.drone_x_pos.get()) + DRONE_X_BASE
        self.y_addr = CANVAS_Y_BASE - int(self.drone_y_pos.get()) - DRONE_Y_BASE
        self.direction = 360 - int(self.drone_direction.get())
        # 高度、速度、バッテリー、飛行時間表示用Scaleの制御変数を定義
        self.koudo_var = IntVar()
        self.koudo_var.set(0)
        self.sokudo_var = IntVar()
        self.sokudo_var.set(0)
        self.dengen_var = IntVar()
        self.dengen_var.set(0)
        self.hikouzikan_var = IntVar()
        self.hikouzikan_var.set(0)

        # ドローンイメージのオブジェクトIDを管理
        self.drone_image_id = 0
        self.drone_arrow_id = 0

        # アプリ内のウィジェットを作成
        self.create_widgets()

    def create_widgets(self):

        # 飛行図面を配置するフレームの作成と配置
        self.canvas_frame = tk.Frame(self.master)
        self.canvas_frame.grid(column=1, row=1)

        # メッセージを配置するフレームの作成と配置
        self.msg_frame = tk.Frame(self.master)
        self.msg_frame.grid(column=2, row=2)

        self.msg_frame11 = tk.Frame(self.msg_frame)
        self.msg_frame11.grid(column=1, row=1)
        self.msg_frame12 = tk.Frame(self.msg_frame)
        self.msg_frame12.grid(column=1, row=2)

        self.msg_frame111 = tk.Frame(self.msg_frame11)
        self.msg_frame111.grid(column=1, row=1, padx=5)
        self.msg_frame112 = tk.Frame(self.msg_frame11)
        self.msg_frame112.grid(column=2, row=1, padx=20)

        # 状態を表示するフレームの作成と配置
        self.state_frame = tk.Frame(self.master)
        self.state_frame.grid(column=2, row=1, padx=10)

        self.state_frame11 = tk.Frame(self.state_frame)
        self.state_frame11.grid(column=1, row=1, pady=10)
        self.state_frame12 = tk.Frame(self.state_frame)
        self.state_frame12.grid(column=1, row=2, pady=10)
        self.state_frame21 = tk.Frame(self.state_frame)
        self.state_frame21.grid(column=2, row=1, pady=10)
        self.state_frame22 = tk.Frame(self.state_frame)
        self.state_frame22.grid(column=2, row=2, pady=10)

        # 制御情報を表示するフレームの作成と配置
        self.control_frame = tk.Frame(self.master)
        self.control_frame.grid(column=1, row=2)

        self.control_frame11 = tk.Frame(self.control_frame)
        self.control_frame11.grid(column=1, row=1)
        self.control_frame12 = tk.Frame(self.control_frame)
        self.control_frame12.grid(column=1, row=2)
        self.control_frame13 = tk.Frame(self.control_frame)
        self.control_frame13.grid(column=1, row=3)
        self.control_frame21 = tk.Frame(self.control_frame)
        self.control_frame21.grid(column=2, row=1)
        self.control_frame22 = tk.Frame(self.control_frame)
        self.control_frame22.grid(column=2, row=2)
        self.control_frame23 = tk.Frame(self.control_frame)
        self.control_frame23.grid(column=2, row=3)
        self.control_frame31 = tk.Frame(self.control_frame)
        self.control_frame31.grid(column=3, row=1)
        self.control_frame32 = tk.Frame(self.control_frame)
        self.control_frame32.grid(column=3, row=2)
        self.control_frame33 = tk.Frame(self.control_frame)
        self.control_frame33.grid(column=3, row=3)
        self.control_frame41 = tk.Frame(self.control_frame)
        self.control_frame41.grid(column=4, row=1)
        self.control_frame42 = tk.Frame(self.control_frame)
        self.control_frame42.grid(column=4, row=2)
        self.control_frame43 = tk.Frame(self.control_frame)
        self.control_frame43.grid(column=4, row=3)

        # キャンバスの作成と配置
        self.main_canvas = tk.Canvas(
            self.canvas_frame,
            width=CANVAS_WIDTH,
            height=CANVAS_HEIGHT,
            bg=CANVAS_BG,
        )
        self.main_canvas.pack()
        self.draw_image()

        # 高度表示
        self.koudo_label = tk.Label(self.state_frame11, text="高度(cm)")
        self.koudo_label.pack()
        self.koudo = tk.Scale(
            self.state_frame11,
            from_=300,
            to=0,
            tickinterval=50,
            orient=VERTICAL,
            variable=self.koudo_var,
        )
        self.koudo.pack()

        # 速度表示
        self.sokudo_label = tk.Label(self.state_frame21, text="速度(cm/s)")
        self.sokudo_label.pack()
        self.sokudo = tk.Scale(
            self.state_frame21,
            from_=100,
            to=0,
            tickinterval=20,
            orient=VERTICAL,
            variable=self.sokudo_var,
        )
        self.sokudo.pack()

        # バッテリ表示
        self.dengen_label = tk.Label(self.state_frame12, text="バッテリ(%)")
        self.dengen_label.pack()
        self.dengen = tk.Scale(
            self.state_frame12,
            from_=100,
            to=0,
            tickinterval=20,
            orient=VERTICAL,
            variable=self.dengen_var,
        )
        self.dengen.pack()

        # バッテリ % の数値表示（#29 / A4）。20% 以下で赤枠で囲って警告する。
        self.dengen_pct = tk.Label(
            self.state_frame12,
            textvariable=self.dengen_var,
            font=("sans-serif", 11, "bold"),
            highlightthickness=2,
            highlightbackground=self.state_frame12.cget("bg"),
        )
        self.dengen_pct.pack(pady=2)

        # 飛行時間表示
        self.hikouzikan_label = tk.Label(self.state_frame22, text="飛行時間(秒)")
        self.hikouzikan_label.pack()
        self.hikouzikan = tk.Scale(
            self.state_frame22,
            from_=600,
            to=0,
            tickinterval=20,
            orient=VERTICAL,
            variable=self.hikouzikan_var,
        )
        self.hikouzikan.pack()

        # ドローンの初期位置(X,Y)の表示ボタン
        self.label1 = tk.Label(
            self.control_frame11,
            anchor=NW,
            #            width=20,
            text="初期位置(X):",
        )
        self.label1.pack()

        self.Entry1 = tk.Entry(self.control_frame21, width=10, textvariable=self.drone_x_pos)
        self.Entry1.pack()

        self.label2 = tk.Label(self.control_frame31, anchor=NW, text="初期位置(Y):")
        self.label2.pack()

        self.Entry2 = tk.Entry(self.control_frame41, width=10, textvariable=self.drone_y_pos)
        self.Entry2.pack()

        self.label3 = tk.Label(self.control_frame12, anchor=NW, text="初期方向:(度)")
        self.label3.pack()

        self.Entry3 = tk.Entry(self.control_frame22, width=10, textvariable=self.drone_direction)
        self.Entry3.pack()

        self.label4 = tk.Label(self.control_frame13, anchor=NW, text="飛行図面:")
        self.label4.pack()

        self.Entry4 = tk.Entry(self.control_frame23, width=10, textvariable=self.gif_file)
        self.Entry4.pack()

        # リセットボタンの作成と配置
        self.reset_button = tk.Button(self.control_frame42, bg="cyan", text="リセット")
        self.reset_button.pack()

        # ファイル読み込みボタンの作成と配置
        self.load_button = tk.Button(self.control_frame43, bg="cyan", text="図面選択")
        self.load_button.pack()

        # メッセージ更新用
        self.message = tk.StringVar()
        self.start_button = tk.Button(self.msg_frame111, bg="green", text="land")
        self.start_button.pack()

        # 緊急停止ボタン（#27 / 検収 A1）: emergency = モータ即停止。
        # 誤操作防止に確認ダイアログを挟む。Ctrl+Space でも発火（Controller.set_events）。
        self.emergency_button = tk.Button(self.msg_frame111, bg="red", fg="white", text="緊急停止")
        self.emergency_button.pack()

        # メッセージ更新用
        self.message = tk.StringVar()
        self.start_button2 = tk.Checkbutton(self.msg_frame112, selectcolor="red", text="通信状態")
        self.start_button2.pack()

        self.message_labelFrame = tk.LabelFrame(
            self.msg_frame12, padx=5, pady=5, text="Telloコマンド:応答"
        )
        self.message_labelFrame.pack()

        self.message_text = tk.Text(
            self.message_labelFrame,
            height=2,
            width=25,
        )
        self.message_text.pack()

        self.message_labelFrame2 = tk.Label(
            self.msg_frame12,
            padx=30,
            pady=0,
            font=("Helvetica", 8),
            text="(C) 2024 Maniwa Net Engineering LLC",
        )
        self.message_labelFrame2.pack()

    def draw_image(self):
        # ドローンと方向矢印を削除
        self.main_canvas.delete(self.drone_image_id)
        self.main_canvas.delete(self.drone_arrow_id)

        # 飛行図面をキャンバスに描画
        self.main_canvas.create_image(50, 20, image=self.gif_image, anchor=NW)
        self.main_canvas.create_line(50, 320, 350, 320, width=2)
        self.main_canvas.create_line(50, 320, 50, 20, width=2)

        #        self.main_canvas.create_line(50 + DRONE_CAGE_P ,320 - DRONE_CAGE_P ,350 - DRONE_CAGE_P ,320 - DRONE_CAGE_P, fill='red', width=2, dash=(3,4))
        #        self.main_canvas.create_line(50 + DRONE_CAGE_P ,320 - DRONE_CAGE_P ,50 + DRONE_CAGE_P ,20 + DRONE_CAGE_P,  fill='red', width=2, dash=(3,4))
        #        self.main_canvas.create_line(350 - DRONE_CAGE_P ,320 - DRONE_CAGE_P ,350 - DRONE_CAGE_P ,20 + DRONE_CAGE_P,  fill='red', width=2, dash=(3,4))
        #        self.main_canvas.create_line(350 - DRONE_CAGE_P ,20 + DRONE_CAGE_P ,50 + DRONE_CAGE_P ,20 + DRONE_CAGE_P,  fill='red', width=2, dash=(3,4))

        for i in range(7):
            x = 50 + (i * 50)
            self.main_canvas.create_line(x, 320, x, 315, width=2)
            self.main_canvas.create_text(x, 324, text=f"{(-15 + 5 * i) - 0}", anchor=N)
        for i in range(7):
            y = 320 - (i * 50)
            self.main_canvas.create_line(50, y, 55, y, width=2)
            self.main_canvas.create_text(46, y, text=f"{(-10 + 5 * i) - 0}", anchor=E)

        self.draw_drone()

    def draw_drone(self):
        # ドローンの開始位置と方向を初期化する
        self.x_addr = (
            CANVAS_X_BASE + (int(self.drone_x_pos.get()) + 750) / DRONE_PIXEL + DRONE_X_BASE
        )
        self.y_addr = (
            CANVAS_Y_BASE - (int(self.drone_y_pos.get()) + 500) / DRONE_PIXEL - DRONE_Y_BASE
        )
        self.direction = 360 - int(self.drone_direction.get())

        # ドローンと方向矢印を描画
        self.drone_image_id = self.main_canvas.create_image(
            self.x_addr, self.y_addr, image=self.drone_image
        )
        self.drone_arrow_id = self.main_canvas.create_line(
            self.x_addr,
            self.y_addr,
            self.x_addr + 12 * math.cos(math.radians(self.direction)),
            self.y_addr + 12 * math.sin(math.radians(self.direction)),
            width=4,
            arrowshape=(6, 6, 3),
            arrow="last",
            fill="red",
        )

    def rand_drone(self):
        # 方向矢印を削除
        self.main_canvas.delete(self.drone_arrow_id)

        # 方向矢印を描画
        self.drone_arrow_id = self.main_canvas.create_line(
            self.x_addr,
            self.y_addr,
            self.x_addr + 12 * math.cos(math.radians(self.direction)),
            self.y_addr + 12 * math.sin(math.radians(self.direction)),
            width=4,
            arrowshape=(6, 6, 3),
            arrow="last",
            fill="red",
        )

    def move_drone(self, kyori, houkou):
        # ドローンと方向矢印を削除
        self.main_canvas.delete(self.drone_image_id)
        self.main_canvas.delete(self.drone_arrow_id)

        # ドローンの移動後の位置を設定する
        self.x_addr = self.x_addr + (kyori * math.cos(math.radians(self.direction - houkou))) / 10
        self.y_addr = self.y_addr + (kyori * math.sin(math.radians(self.direction - houkou))) / 10

        # ドローンと方向矢印を描画
        self.drone_image_id = self.main_canvas.create_image(
            self.x_addr, self.y_addr, image=self.drone_image
        )
        self.drone_arrow_id = self.main_canvas.create_line(
            self.x_addr,
            self.y_addr,
            self.x_addr + 12 * math.cos(math.radians(self.direction)),
            self.y_addr + 12 * math.sin(math.radians(self.direction)),
            width=4,
            arrowshape=(6, 6, 3),
            arrow="last",
            fill="red",
        )

    def draw_message(self, message):
        self.message_text.delete("1.0", END)
        self.message_text.insert("1.0", message)

    def set_battery_warning(self, low):
        "バッテリ 20% 以下のとき % 表示を赤枠で囲う（#29 / A4）。"
        if low:
            self.dengen_pct.configure(highlightbackground="red", fg="red")
        else:
            normal = self.state_frame12.cget("bg")
            self.dengen_pct.configure(highlightbackground=normal, fg="black")

    def select_file(self):
        "ファイル選択画面を表示"
        file_path = tk.filedialog.askopenfilename(initialdir=".")
        return file_path


class Controller:
    INTERVAL = 200
    HEALTH_COUNTER = 50

    def __init__(self, app, view):
        self.master = app
        self.view = view

        # ラベル表示メッセージ管理用
        self.message = ""

        # 飛行中フラグ（#29 / A3）: 通信断の自動着陸は飛行中のみ・1 回だけ送る。
        self.airborne = False

        self.set_events()

    def set_events(self):
        "受け付けるイベントを設定する"

        # 読み込みボタン押し下げイベント受付
        self.view.load_button["command"] = self.push_load_button
        self.view.reset_button["command"] = self.push_reset_button

        # 緊急停止（#27 / A1）: ボタンと Ctrl+Space ショートカット
        self.view.emergency_button["command"] = self.push_emergency
        self.master.bind("<Control-space>", lambda _e: self.push_emergency())

        # 画像の描画用のタイマーセット
        self.master.after(Controller.INTERVAL, self.timer)

    def push_emergency(self):
        "緊急停止ボタン/Ctrl+Space: 確認後に emergency（モータ即停止）を送信する"
        if not tk.messagebox.askyesno("緊急停止", "全モータを即停止します。よろしいですか？"):
            return
        trn_msg = com.send_cmd(commands.build_command("emergency"))
        self.view.draw_message(f"emergency:{trn_msg}")

    def timer(self):
        "一定間隔で各種処理を実行する"

        # Webメッセージの受信状況を確認する
        self.check_queue()
        self.check_err_queue()
        if Controller.HEALTH_COUNTER < 100:
            Controller.HEALTH_COUNTER = Controller.HEALTH_COUNTER + 1

        if Controller.HEALTH_COUNTER >= 50:
            self.view.start_button2.configure(selectcolor="red")
        else:
            self.view.start_button2.configure(selectcolor="green")

        # 通信断 3 秒で自動着陸（#29 / A3）。飛行中のみ・1 回だけ land を送る。
        if self.airborne and safety.should_autoland(Controller.HEALTH_COUNTER, Controller.INTERVAL):
            com.send_cmd("land")
            self.airborne = False
            self.view.draw_message("通信断: 自動着陸しました")

        # バッテリ 20% 以下で % 表示を赤枠化（#29 / A4）
        self.view.set_battery_warning(safety.is_low_battery(self.view.dengen_var.get()))

        # 再度タイマー設定
        self.master.after(Controller.INTERVAL, self.timer)

    def check_queue(self):
        if not msg_queue.empty():
            message = msg_queue.get()
            #            print("check_queue#Start,message: %s" % message)
            #            print("\nreceve_forever#Recv,bat:%s " % val.split(':')[1])
            #            self.view.draw_message(message)

            self.view.draw_message(message + ":ok")

            message = message + "//"
            opcode = message.split("/")[1]
            param = message.split("/")[2]
            #            print("check_queue# op:" + opcode + " param:" + param )

            if opcode == "command":
                return

            elif opcode == "takeoff":
                self.view.start_button.configure(bg="cyan")
                self.view.start_button.configure(text="takeoff")
                self.airborne = True  # 飛行中（#29 / A3）
                return

            elif opcode == "land":
                self.view.start_button.configure(bg="green")
                self.view.start_button.configure(text="land")
                self.airborne = False  # 着陸済み（#29 / A3）
                return

            elif opcode == "emergency":
                self.view.start_button.configure(bg="red")
                self.view.start_button.configure(text="emergency")
                return

            elif opcode == "up":
                return

            elif opcode == "down":
                return

            elif opcode == "left":
                self.view.move_drone(int(param), 90)

            elif opcode == "right":
                self.view.move_drone(int(param), 270)

            elif opcode == "forward":
                #                print("check_queue#forward,param: %s" % param)
                self.view.move_drone(int(param), 0)

            elif opcode == "back":
                self.view.move_drone(int(param), 180)

            elif opcode == "ccw":
                if self.view.direction - int(param) < 0:
                    self.view.direction = self.view.direction - int(param) + 360
                else:
                    self.view.direction = self.view.direction - int(param)

                self.view.rand_drone()

            elif opcode == "cw":
                if self.view.direction + int(param) > 360:
                    self.view.direction = self.view.direction + int(param) - 360
                else:
                    self.view.direction = self.view.direction + int(param)

                self.view.rand_drone()

            elif opcode == "flip":
                return

            elif opcode == "setspeed":
                return

            elif opcode == "streamon":
                return

            elif opcode == "streamoff":
                return

            elif opcode == "flip":
                return

            elif opcode == "dwonvision":
                return

            elif opcode == "streamwrite":
                return

            else:
                print("ERROR")
                return

    def check_err_queue(self):
        if not err_queue.empty():
            message = err_queue.get()
            #            print(message)
            self.view.draw_message(message)

    def push_load_button(self):
        "ファイル選択ボタンが押された時の処理"

        # ファイル選択画面表示
        gif_file = self.view.select_file()
        self.view.gif_file.set(gif_file)

        # 画像ファイルの読み込みと描画
        if len(gif_file) != 0:
            self.view.gif_image = tk.PhotoImage(file=gif_file)
            self.view.draw_image()
            # メッセージを描画
            self.message = "飛行図面を変更しました"
            self.view.draw_message(self.message)

    def push_reset_button(self):
        "ファイル選択ボタンが押された時の処理"

        self.view.main_canvas.delete(self.view.drone_image_id)
        self.view.main_canvas.delete(self.view.drone_arrow_id)
        self.view.draw_drone()


# --- main ---
def main():

    # 機体番号（映像転送ポートとビーコン id に使う。既定 1）
    parser = argparse.ArgumentParser(description="tellomon（Pi 側 Tello 制御）")
    parser.add_argument(
        "--drone", type=int, default=1, choices=range(1, 5), help="機体番号 1〜4（既定: 1）"
    )
    parser.add_argument(
        "--beacon-host",
        default=NOTE_PC_IP,
        help=f"ビーコン送信先ホスト（既定: {NOTE_PC_IP}。ローカル確認は 127.0.0.1）",
    )
    args = parser.parse_args()
    drone_num = args.drone

    # コマンド送信用ソケットの作成
    #    com = ComHandler()

    # ルートウィンドウの作成
    root = tk.Tk()
    root.geometry(WINDOW_SIZE)
    root.title(WINDOW_TITLE)

    view = View(root)
    Controller(root, view)

    #
    # Webサーバ用のを起動する
    #   port番号:8001
    #
    webServer = HTTPServer(("0.0.0.0", 8001), HttpHandler)
    t1 = threading.Thread(target=webServer.serve_forever, daemon=True)
    t1.start()

    recv = StatusRecever(view)
    t2 = threading.Thread(target=recv.receve_forever, daemon=True)
    t2.start()

    t3 = threading.Thread(target=run_udp_receiver, args=(drone_num,))
    t3.daemon = True
    t3.start()

    # ビーコン送信スレッド（status を 1Hz に間引いてノートPCへ JSON 送信）
    # #31: status に dead-reckoning の想定位置 x/y を合流させてビーコンへ載せる。
    # DRONE_STATE はコマンド毎に再代入されるグローバルなので、呼び出し時に都度読む。
    def _status_with_position():
        return {**recv.latest, "x": DRONE_STATE.x, "y": DRONE_STATE.y}

    beacon_sender = BeaconSender(drone_num, _status_with_position, host=args.beacon_host)
    beacon_sender.start()

    try:
        root.mainloop()
    finally:
        beacon_sender.stop()


if __name__ == "__main__":
    main()
