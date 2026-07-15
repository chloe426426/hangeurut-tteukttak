from flask import Flask, jsonify, send_from_directory, Response, request
from flask_cors import CORS
from datetime import datetime
import json, os, time, threading
import urllib.request, urllib.parse, re

app = Flask(__name__)
CORS(app)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

NEIS_KEY = "여기에_발급받은_인증키_입력"
NEIS_OFFICE_CODE = "K10"
NEIS_SCHOOL_CODE = "7801101"

CLOUD_SECRET = "hangeurut2026secret"  # 미니PC 쪽과 반드시 동일해야 함

lock = threading.Lock()
latest_status = {"count": 0, "waitMinutes": 0, "updatedAt": None}
latest_frame = {"bytes": None, "updatedAt": 0}
_menu_cache = {"date": None, "data": None}


def check_secret():
    return request.headers.get("X-Secret") == CLOUD_SECRET


@app.route("/")
def home():
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/manifest.json")
def manifest():
    return send_from_directory(BASE_DIR, "manifest.json")


@app.route("/icon-192.png")
def icon_192():
    return send_from_directory(BASE_DIR, "icon-192.png")


@app.route("/icon-512.png")
def icon_512():
    return send_from_directory(BASE_DIR, "icon-512.png")


# 미니PC → 클라우드: 인원수/대기시간
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


# 미니PC → 클라우드: 영상 프레임
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


def fetch_neis_menu():
    today = datetime.now().strftime("%Y%m%d")
    if _menu_cache["date"] == today and _menu_cache["data"]:
        return _menu_cache["data"]
    params = {"KEY": NEIS_KEY, "Type": "json", "ATPT_OFCDC_SC_CODE": NEIS_OFFICE_CODE,
              "SD_SCHUL_CODE": NEIS_SCHOOL_CODE, "MLSV_YMD": today}
    url = "https://open.neis.go.kr/hub/mealServiceDietInfo?" + urllib.parse.urlencode(params)
    result = {"date": today, "breakfast": [], "lunch": [], "dinner": []}
    try:
        raw = urllib.request.urlopen(url, timeout=5).read().decode("utf-8")
        data = json.loads(raw)
        meal_info = data.get("mealServiceDietInfo", [None, {}])
        rows = meal_info[1].get("row", []) if len(meal_info) > 1 else []
        for row in rows:
            dishes = re.sub(r"\([\d.]+\)", "", row.get("DDISH_NM", ""))
            items = [d.strip() for d in dishes.split("<br/>") if d.strip()]
            name = row.get("MMEAL_SC_NM", "")
            if "조식" in name: result["breakfast"] = items
            elif "중식" in name: result["lunch"] = items
            elif "석식" in name: result["dinner"] = items
    except Exception as e:
        print("나이스 급식 정보 조회 실패:", e)
    _menu_cache["date"] = today
    _menu_cache["data"] = result
    return result


@app.route("/api/menu")
def api_menu():
    return jsonify(fetch_neis_menu())


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
