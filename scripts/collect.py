"""제주 1인 세대 살핌판 · 자료 모으기 (GitHub Actions에서 실행)

행정안전부_법정동별(행정동 통반단위) 성/연령별 주민등록 1인세대수 오픈API를 불러
제주 읍면동별 · 성별 · 나이대별 1인 세대 수로 합친 뒤 data/single.json 에 달별로 쌓습니다.

- 인증키는 GitHub Settings > Secrets > Actions 의 PUBLIC_API_KEY 에만 둡니다.
- 결과 파일과 오류 문구에는 키를 넣지 않습니다(*** 로 가림).
- 주민등록 통계는 한 달에 한 번 바뀌므로, 이미 받은 달이면 아무것도 바꾸지 않습니다.

[확인 필요] 아래 CONFIG 의 주소 · 요청 항목 · 응답 항목 이름은 공공데이터포털 상세 페이지의
"요청변수 / 출력결과" 표를 보고 맞춥니다. 지금 값은 자리만 잡아 둔 것입니다.
"""
import json, os, sys, time, urllib.parse, urllib.request
from datetime import date

CONFIG = {
    "endpoint": "https://apis.data.go.kr/1741000/확인필요/확인필요",  # [확인 필요] 요청주소(End Point)
    "params": {                       # [확인 필요] 요청변수 이름과 값
        "admmCd": "5000000000",       # 제주특별자치도 행정기관코드 (이름 확인 필요)
        "srchFrYm": "{ym}",           # 조회 시작 연월 (이름 확인 필요)
        "srchToYm": "{ym}",           # 조회 끝 연월 (이름 확인 필요)
        "lv": "4",                    # 조회 단위: 통반 (값 확인 필요)
        "type": "JSON",
        "numOfRows": "1000",
    },
    "fields": {                       # [확인 필요] 출력결과 항목 이름
        "city": "sggNm",              # 시군구 이름 (제주시, 서귀포시)
        "dong": "dongNm",             # 행정동 이름 (읍면동)
        "sex": "sexdNm",              # 성별 (남, 여)
        "age_cols": {                 # 나이대 칸 이름 → 화면 나이대
            "확인필요_0": "20세 미만", "확인필요_10": "20세 미만",
            "확인필요_20": "20대", "확인필요_30": "30대", "확인필요_40": "40대",
            "확인필요_50": "50대", "확인필요_60": "60대", "확인필요_70": "70대",
            "확인필요_80": "80세 이상", "확인필요_90": "80세 이상", "확인필요_100": "80세 이상",
        },
    },
}
AGES = ["20세 미만", "20대", "30대", "40대", "50대", "60대", "70대", "80세 이상"]
OUT = "data/single.json"
KEEP_MONTHS = 25
KEY = os.environ.get("PUBLIC_API_KEY", "")


def hide(text):
    return str(text).replace(KEY, "***") if KEY else str(text)


def fetch_month(ym):
    rows, page = [], 1
    while True:
        q = {k: v.replace("{ym}", ym) for k, v in CONFIG["params"].items()}
        q.update({"serviceKey": KEY, "pageNo": str(page)})
        url = CONFIG["endpoint"] + "?" + urllib.parse.urlencode(q)
        with urllib.request.urlopen(url, timeout=60) as r:
            body = json.loads(r.read().decode("utf-8"))
        # [확인 필요] 응답 구조: response > header(resultCode) > body > items > item 로 가정
        res = body.get("response", body)
        code = str(res.get("header", {}).get("resultCode", "00"))
        if code not in ("00", "0", "0000"):
            raise RuntimeError("결과 코드 " + code + " " + res.get("header", {}).get("resultMsg", ""))
        items = res.get("body", {}).get("items", {})
        items = items.get("item", items) if isinstance(items, dict) else items
        if isinstance(items, dict):
            items = [items]
        rows += items or []
        total = int(res.get("body", {}).get("totalCount", len(rows)))
        if len(rows) >= total or not items:
            return rows
        page += 1
        time.sleep(0.3)


def to_dong(rows):
    """통 · 반 줄을 읍면동으로 합침. 화면에는 읍면동까지만 보여 줌."""
    f = CONFIG["fields"]
    out = {}
    for r in rows:
        dong, city = r.get(f["dong"]), r.get(f["city"])
        if not dong:
            continue
        d = out.setdefault(dong, {"city": city, "M": [0] * len(AGES), "F": [0] * len(AGES)})
        side = "M" if str(r.get(f["sex"], "")).startswith("남") else "F"
        for col, band in f["age_cols"].items():
            try:
                d[side][AGES.index(band)] += int(float(r.get(col, 0) or 0))
            except ValueError:
                pass
    return out


def months_to_try():
    t = date.today().replace(day=1)
    out = []
    for back in (1, 2):  # 지난달 자료가 아직 없으면 그 전 달
        y, m = t.year, t.month - back
        while m <= 0:
            y, m = y - 1, m + 12
        out.append(f"{y}{m:02d}")
    return out


def main():
    if not KEY:
        sys.exit("PUBLIC_API_KEY 가 없습니다. Settings > Secrets and variables > Actions 에 넣어 주세요.")
    os.makedirs("data", exist_ok=True)
    try:
        data = json.load(open(OUT, encoding="utf-8"))
    except Exception:
        data = {}
    if data.get("sample"):          # 가상 예시 파일이면 비우고 실제 자료로 시작
        data = {}
    data.setdefault("months", {})
    data.update({"sample": False, "ages": AGES,
                 "source": "행정안전부_법정동별(행정동 통반단위) 성/연령별 주민등록 1인세대수 (공공데이터포털)"})

    wanted = months_to_try()
    latest = wanted[0]
    # 작년 같은 달도 없으면 함께 받아 1년 비교를 바로 할 수 있게 함
    targets = []
    for ym in wanted:
        if ym in data["months"]:
            print(ym, "이미 받은 달입니다. 바꿀 것이 없습니다.")
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
        # 보고서는 지난달 · 작년 같은 달과 비교하므로, 없으면 함께 받음
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
