"""제주 1인 세대 살핌 · 자료 모으기 (GitHub Actions에서 실행)
행정안전부_법정동별(행정동 통반단위) 성/연령별 주민등록 1인세대수 (공공데이터포털 15108085)
키는 GitHub Secrets 의 PUBLIC_API_KEY 에만 둡니다. 로그와 파일에는 키를 *** 로 가립니다.
"""
import json, os, sys, time, urllib.parse, urllib.request
from datetime import date

CONFIG = {
    "endpoint": "https://apis.data.go.kr/1741000/stdgSexdAgeOneHh/selectStdgSexdAgeOneHh",
    "params": {
        "stdgCd": "5000000000",   # 제주특별자치도 (법정동코드)
        "srchFrYm": "{ym}",       # 조회 시작 연월
        "srchToYm": "{ym}",       # 조회 끝 연월
        "lv": "3",                # 3 = 읍면동 단위
        "regSeCd": "1",           # 1 = 전체
        "type": "JSON",
        "numOfRows": "100",
    },
    "fields": {
        "city": "sggNm", "dong": "dongNm", "dong_alt": "stdgNm",
        "age_cols": {"0": "20세 미만", "10": "20세 미만", "20": "20대", "30": "30대", "40": "40대", "50": "50대", "60": "60대", "70": "70대", "80": "80세 이상", "90": "80세 이상", "100": "80세 이상"},
    },
}
AGES = ["20세 미만", "20대", "30대", "40대", "50대", "60대", "70대", "80세 이상"]
OUT = "data/single.json"
KEEP_MONTHS = 25
KEY = os.environ.get("PUBLIC_API_KEY", "")


def hide(text):
    return str(text).replace(KEY, "***") if KEY else str(text)


def find(obj, key):
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            got = find(v, key)
            if got is not None:
                return got
    elif isinstance(obj, list):
        for v in obj:
            got = find(v, key)
            if got is not None:
                return got
    return None


def fetch_month(ym):
    rows, page = [], 1
    while True:
        q = {k: v.replace("{ym}", ym) for k, v in CONFIG["params"].items()}
        q.update({"serviceKey": KEY, "pageNo": str(page)})
        url = CONFIG["endpoint"] + "?" + urllib.parse.urlencode(q)
        with urllib.request.urlopen(url, timeout=60) as r:
            raw = r.read().decode("utf-8", "replace")
        try:
            body = json.loads(raw)
        except ValueError:
            raise RuntimeError("JSON 이 아닌 응답: " + raw[:300])
        code = str(find(body, "resultCode") or "00")
        if code not in ("00", "0", "0000", "INFO-0"):
            raise RuntimeError("결과 코드 " + code + " " + str(find(body, "resultMsg") or ""))
        items = find(body, "item")
        if items is None:
            items = find(body, "items") or []
        if isinstance(items, dict):
            items = [items]
        rows += items
        total = int(find(body, "totalCount") or len(rows))
        if page == 1:
            print(ym, "전체", total, "줄")
        if len(rows) >= total or not items:
            return rows
        page += 1
        time.sleep(0.3)


def to_dong(rows):
    f = CONFIG["fields"]
    out = {}
    for r in rows:
        dong = r.get(f["dong"]) or r.get(f["dong_alt"])
        if not dong:
            continue
        d = out.setdefault(dong, {"city": r.get(f["city"]), "M": [0] * len(AGES), "F": [0] * len(AGES)})
        for n, band in f["age_cols"].items():
            i = AGES.index(band)
            for side, pre in (("M", "male"), ("F", "feml")):
                try:
                    d[side][i] += int(float(r.get(f"{pre}{n}AgeHhCnt") or 0))
                except ValueError:
                    pass
    return out


def months_to_try():
    t = date.today().replace(day=1)
    out = []
    for back in (1, 2):
        y, m = t.year, t.month - back
        while m <= 0:
            y, m = y - 1, m + 12
        out.append(f"{y}{m:02d}")
    return out


def main():
    if not KEY:
        sys.exit("PUBLIC_API_KEY 가 없습니다.")
    os.makedirs("data", exist_ok=True)
    try:
        data = json.load(open(OUT, encoding="utf-8"))
    except Exception:
        data = {}
    if data.get("sample"):
        data = {}
    data.setdefault("months", {})
    data.update({"sample": False, "ages": AGES,
                 "source": "행정안전부_법정동별(행정동 통반단위) 성/연령별 주민등록 1인세대수 (공공데이터포털)"})
    targets = []
    for ym in months_to_try():
        if ym in data["months"]:
            print(ym, "이미 받은 달입니다.")
            break
        targets.append(ym)
    changed = False
    for ym in targets:
        try:
            rows = fetch_month(ym)
        except Exception as e:
            print(ym, "받기 실패:", hide(e))
            continue
        if not rows:
            print(ym, "아직 자료가 없습니다.")
            continue
        data["months"][ym] = to_dong(rows)
        print(ym, "저장:", len(data["months"][ym]), "개 읍면동")
        changed = True
        y, m = int(ym[:4]), int(ym[4:])
        last = f"{y}{m - 1:02d}" if m > 1 else f"{y - 1}12"
        for extra, why in ((last, "지난달"), (f"{y - 1}{m:02d}", "작년 같은 달")):
            if extra in data["months"]:
                continue
            try:
                prow = fetch_month(extra)
                if prow:
                    data["months"][extra] = to_dong(prow)
                    print(extra, why, "자료도 저장")
            except Exception as e:
                print(extra, why, "받기 실패:", hide(e))
        break
    if not changed:
        return
    for old in sorted(data["months"])[:-KEEP_MONTHS]:
        del data["months"][old]
    data["fetchedAt"] = date.today().isoformat()
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    if KEY and KEY in text:
        sys.exit("결과에 키가 섞여 저장하지 않습니다.")
    open(OUT, "w", encoding="utf-8").write(text)


if __name__ == "__main__":
    main()
