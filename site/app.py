from flask import Flask, jsonify, send_from_directory, Response, request
from flask_cors import CORS
from datetime import datetime
import os, time, threading
from neis_menu import get_menu

app = Flask(__name__)
CORS(app)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CLOUD_SECRET = "hangeurut2026secret"  # 미니PC 쪽과 반드시 동일해야 함
CAMERA_TIMEOUT_SEC = 5   # 이 시간 동안 새 프레임이 없으면 카메라 꺼진 것으로 판단
ALARM_TTL = 60           # 이 시간 동안 소식 없으면 알림 자동 해제(앱을 껐다는 뜻)

lock = threading.Lock()
latest_status = {"count": 0, "waitMinutes": 0, "updatedAt": None}
latest_frame = {"bytes": None, "updatedAt": 0}

_alarms = {}                    # 알림 신청자 ID -> 마지막 신호 시각
_alarm_lock = threading.Lock()


def check_secret():
    return request.headers.get("X-Secret") == CLOUD_SECRET


def alarm_count():
    now = time.time()
    with _alarm_lock:
        for k in [k for k, t in _alarms.items() if now - t > ALARM_TTL]:
            del _alarms[k]
        return len(_alarms)


@app.route("/")
def home():
    return send_from_directory(os.path.join(BASE_DIR, "templates"), "index.html")


@app.route("/manifest.json")
def manifest():
    return send_from_directory(os.path.join(BASE_DIR, "static"), "manifest.json")


@app.route("/icon-192.png")
def icon_192():
    return send_from_directory(os.path.join(BASE_DIR, "static"), "icon-192.png")


@app.route("/icon-512.png")
def icon_512():
    return send_from_directory(os.path.join(BASE_DIR, "static"), "icon-512.png")


# 미니PC → 클라우드: 인원수/대기시간 수신
@app.route("/api/update", methods=["POST"])
def api_update():
    if not check_secret():
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json(force=True, silent=True) or {}
    with lock:
        latest_status["count"] = data.get("count", 0)
        latest_status["waitMinutes"] = data.get("waitMinutes", 0)
        latest_status["updatedAt"] = datetime.now().isoformat()
    return jsonify({"ok": True})


# 미니PC → 클라우드: 영상 프레임 수신
@app.route("/api/frame", methods=["POST"])
def api_frame():
    if not check_secret():
        return jsonify({"error": "unauthorized"}), 401
    with lock:
        latest_frame["bytes"] = request.get_data()
        latest_frame["updatedAt"] = time.time()
    return jsonify({"ok": True})


@app.route("/api/status")
def api_status():
    with lock:
        status = dict(latest_status)
        frame_updated = latest_frame["updatedAt"]
    status["camera_live"] = bool(frame_updated) and (time.time() - frame_updated < CAMERA_TIMEOUT_SEC)
    status["alarm_count"] = alarm_count()
    return jsonify(status)


# 알림 설정/취소 - 몇 명이 대기 중인지 집계
@app.route("/api/alarm", methods=["POST"])
def api_alarm():
    d = request.get_json(force=True, silent=True) or {}
    sid = str(d.get("id", ""))[:64]
    if not sid:
        return jsonify({"ok": False, "error": "id 없음"}), 400
    with _alarm_lock:
        if d.get("on"):
            _alarms[sid] = time.time()
        else:
            _alarms.pop(sid, None)
    return jsonify({"ok": True, "alarm_count": alarm_count()})


@app.route("/api/menu")
def api_menu():
    return jsonify(get_menu())


def generate_frames():
    last_sent = 0
    while True:
        with lock:
            frame_bytes = latest_frame["bytes"]
            updated_at = latest_frame["updatedAt"]
        if frame_bytes and updated_at != last_sent:
            last_sent = updated_at
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        time.sleep(0.1)


@app.route("/video")
def video():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)