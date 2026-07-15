import os, json, re
import urllib.request, urllib.parse
from datetime import datetime
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

PUSH_SECRET = os.environ.get("PUSH_SECRET", "바꿔주세요아무문자열")

NEIS_KEY = "발급받은_인증키"
NEIS_OFFICE_CODE = "K10"
NEIS_SCHOOL_CODE = "7801101"
_menu_cache = {"date": None, "data": None}

state = {"count": 0, "waitMinutes": 0, "updatedAt": None}


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/status")
def api_status():
    return jsonify(state)


@app.route("/api/update", methods=["POST"])
def api_update():
    if request.headers.get("X-Secret") != PUSH_SECRET:
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json(force=True)
    state["count"] = data.get("count", 0)
    state["waitMinutes"] = data.get("waitMinutes", 0)
    state["updatedAt"] = datetime.now().isoformat()
    return jsonify({"ok": True})


def fetch_neis_menu():
    today = datetime.now().strftime("%Y%m%d")
    if _menu_cache["date"] == today and _menu_cache["data"]:
        return _menu_cache["data"]
    params = {"KEY": NEIS_KEY, "Type": "json", "ATPT_OFCDC_SC_CODE": NEIS_OFFICE_CODE,
              "SD_SCHUL_CODE": NEIS_SCHOOL_CODE, "MLSV_YMD": today}
    url = "https://open.neis.go.kr/hub/mealServiceDietInfo?" + urllib.parse.urlencode(params)
    result = {"date": today, "breakfast": [], "lunch": [], "dinner": []}
    try:
        with urllib.request.urlopen(url, timeout=5) as res:
            data = json.loads(res.read().decode("utf-8"))
        rows = data.get("mealServiceDietInfo", [None, {}])[1].get("row", [])
        for row in rows:
            dishes = re.sub(r"\([\d.]+\)", "", row.get("DDISH_NM", ""))
            items = [d.strip() for d in dishes.split("<br/>") if d.strip()]
            m = row.get("MMEAL_SC_NM", "")
            if "조식" in m: result["breakfast"] = items
            elif "중식" in m: result["lunch"] = items
            elif "석식" in m: result["dinner"] = items
    except Exception as e:
        print("나이스 실패:", e)
    _menu_cache["date"] = today
    _menu_cache["data"] = result
    return result


@app.route("/api/menu")
def api_menu():
    return jsonify(fetch_neis_menu())


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))