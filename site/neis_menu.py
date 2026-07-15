"""
neis_menu.py - 나이스(NEIS) 급식 연동
"""

import re
import datetime
import threading

import requests

NEIS_KEY = "78bb6d662d8b404d82fd91c4ec050c25"
OFFICE_CODE = "K10"
SCHOOL_NAME = "강원과학고등학교"
SCHOOL_CODE = ""

SHOW_ALLERGY_NO = False
TIMEOUT = 8

BASE = "https://open.neis.go.kr/hub"
_cache = {"date": None, "data": None}
_lock = threading.Lock()
_school_code = None


def _clean(dish: str) -> str:
    d = dish.replace("<br/>", "").strip()
    if SHOW_ALLERGY_NO:
        return d
    d = re.sub(r"\s*\(\s*[\d.\s]+\)\s*$", "", d)
    d = re.sub(r"\s*[\d.]+\s*$", "", d)
    return d.strip()


def _find_school_code() -> str:
    global _school_code
    if _school_code:
        return _school_code
    if SCHOOL_CODE:
        _school_code = SCHOOL_CODE
        return _school_code

    params = {
        "KEY": NEIS_KEY, "Type": "json",
        "ATPT_OFCDC_SC_CODE": OFFICE_CODE,
        "SCHUL_NM": SCHOOL_NAME,
    }
    r = requests.get(f"{BASE}/schoolInfo", params=params, timeout=TIMEOUT)
    data = r.json()

    if "schoolInfo" not in data:
        msg = data.get("RESULT", {}).get("MESSAGE", "학교를 찾지 못했습니다")
        raise RuntimeError(f"학교코드 조회 실패: {msg}")

    rows = data["schoolInfo"][1]["row"]
    _school_code = rows[0]["SD_SCHUL_CODE"]
    print(f"[나이스] 학교코드 확인: {rows[0]['SCHUL_NM']} = {_school_code}")
    return _school_code


def _date_label(d: datetime.date) -> str:
    w = ["월", "화", "수", "목", "금", "토", "일"][d.weekday()]
    return f"{d.month}. {d.day} ({w})"


def fetch_menu(day: datetime.date = None) -> dict:
    day = day or datetime.date.today()
    code = _find_school_code()

    params = {
        "KEY": NEIS_KEY, "Type": "json",
        "ATPT_OFCDC_SC_CODE": OFFICE_CODE,
        "SD_SCHUL_CODE": code,
        "MLSV_YMD": day.strftime("%Y%m%d"),
    }
    r = requests.get(f"{BASE}/mealServiceDietInfo", params=params, timeout=TIMEOUT)
    data = r.json()

    out = {"date": _date_label(day), "breakfast": [], "lunch": [], "dinner": []}

    if "mealServiceDietInfo" not in data:
        code_ = data.get("RESULT", {}).get("CODE", "")
        if code_ != "INFO-200":
            print(f"[나이스] 급식 조회 응답: {data.get('RESULT', {}).get('MESSAGE', data)}")
        return out

    slot = {"조식": "breakfast", "중식": "lunch", "석식": "dinner"}
    for row in data["mealServiceDietInfo"][1]["row"]:
        key = slot.get(row.get("MMEAL_SC_NM", "").strip())
        if not key:
            continue
        dishes = [_clean(x) for x in row["DDISH_NM"].split("<br/>")]
        out[key] = [d for d in dishes if d]
    return out


def get_menu() -> dict:
    today = datetime.date.today()
    with _lock:
        if _cache["date"] == today and _cache["data"]:
            return _cache["data"]
        try:
            data = fetch_menu(today)
            _cache["date"], _cache["data"] = today, data
            n = sum(len(data[k]) for k in ("breakfast", "lunch", "dinner"))
            print(f"[나이스] 급식 갱신 완료: {today} · 총 {n}개 메뉴")
            return data
        except Exception as e:
            print(f"[나이스] 실패: {e}")
            if _cache["data"]:
                return _cache["data"]
            return {"date": _date_label(today), "breakfast": [], "lunch": [], "dinner": []}


def refresh_loop(interval_sec=1800):
    import time
    while True:
        get_menu()
        time.sleep(interval_sec)


if __name__ == "__main__":
    import json
    print(json.dumps(get_menu(), ensure_ascii=False, indent=2))