from flask import Flask, jsonify, send_from_directory, Response, request
from flask_cors import CORS
from datetime import datetime
import os, time, threading
from neis_menu import get_menu

app = Flask(__name__)
CORS(app)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CLOUD_SECRET = "hangeurut2026secret"  # 미니PC 쪽과 반드시 동일해야 함

lock = threading.Lock()
latest_status = {"count": 0, "waitMinutes": 0, "updatedAt": None}
latest_frame = {"bytes": None, "updatedAt": 0}


def check_secret():
    return request.headers.get("X-Secret") == CLOUD_SECRET


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
        return jsonify(dict(latest_status))


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