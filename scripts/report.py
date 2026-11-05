"""제주 1인 세대 살핌 · 월간 보고서 만들기 (외부 AI 없이 계산 + 문장 틀)

data/single.json 의 달별 자료로 달마다 보고서를 만듭니다.
- data/reports.json : 화면(index.html)이 읽는 보고서 모음
- reports/YYYYMM.md : GitHub Issue 본문으로 올릴 마크다운 (새 달만)
새 보고서가 생기면 GITHUB_OUTPUT 에 new_report=경로 를 적어, 워크플로가 Issue 를 올리게 합니다.

기준(RULES)은 아래 숫자만 바꾸면 됩니다. 기준을 바꾸면 README 의 "기준" 표도 함께 고칩니다.
"""
import json, os

RULES = {
    "old_month_up": 10,      # 80세 이상 1인 세대가 지난달보다 이 수 이상 늘면
    "young_month_pct": 8.0,  # 청년(20~30대) 1인 세대가 지난달보다 이 % 이상 늘고
    "young_month_min": 20,   #   그 수가 이 세대 이상이면
    "old_share": 20.0,       # 동 1인 세대 중 80세 이상 비중이 이 % 이상이고
    "old_share_up": 0.5,     #   지난달보다 이 %p 이상 오르면
    "old_year_pct": 8.0,     # 80세 이상 1인 세대가 작년 같은 달보다 이 % 이상 늘면
    "pick": 3,               # "이달 먼저 살펴볼 동" 수
}
DATA, OUT, MD_DIR = "data/single.json", "data/reports.json", "reports"


def ym_shift(ym, months):
    y, m = int(ym[:4]), int(ym[4:]) + months
    while m <= 0:
        y, m = y - 1, m + 12
    while m > 12:
        y, m = y + 1, m - 12
    return f"{y}{m:02d}"


def label(ym):
    return f"{ym[:4]}년 {int(ym[4:])}월 말"


def pick(row, ages, names):
    ix = [ages.index(a) for a in names]
    return sum(row["M"][i] + row["F"][i] for i in ix)


def total(row):
    return sum(row["M"]) + sum(row["F"])


def build(data, ym):
    ages, M = data["ages"], data["months"]
    cur, prev, year = M[ym], M.get(ym_shift(ym, -1)), M.get(ym_shift(ym, -12))
    if prev is None:
        return None
    OLD, YOUNG = ["80세 이상"], ["20대", "30대"]
    rows = []
    for dong, r in cur.items():
        p = prev.get(dong)
        if not p:
            continue
        t, pt = total(r), total(p)
        o, po = pick(r, ages, OLD), pick(p, ages, OLD)
        y, py = pick(r, ages, YOUNG), pick(p, ages, YOUNG)
        yo = pick(year[dong], ages, OLD) if year and dong in year else None
        share = o / t * 100 if t else 0
        pshare = po / pt * 100 if pt else 0
        hits = []
        if o - po >= RULES["old_month_up"]:
            hits.append("80세 이상 한 달 증가")
        if py and (y - py) / py * 100 >= RULES["young_month_pct"] and y - py >= RULES["young_month_min"]:
            hits.append("청년 급증")
        if share >= RULES["old_share"] and share - pshare >= RULES["old_share_up"]:
            hits.append("80세 이상 비중 높음")
        if yo and (o - yo) / yo * 100 >= RULES["old_year_pct"]:
            hits.append("80세 이상 1년 증가")
        rows.append({"dong": dong, "city": r["city"], "total": t, "totalDiff": t - pt,
                     "old": o, "oldDiff": o - po, "oldYearPct": round((o - yo) / yo * 100, 1) if yo else None,
                     "young": y, "youngDiff": y - py, "youngPct": round((y - py) / py * 100, 1) if py else None,
                     "oldShare": round(share, 1), "oldShareDiff": round(share - pshare, 1), "hits": hits})
    flagged = sorted([r for r in rows if r["hits"]], key=lambda r: (-len(r["hits"]), -r["oldDiff"], -r["youngDiff"]))
    top = flagged[:RULES["pick"]]
    T, PT = sum(r["total"] for r in rows), sum(r["total"] - r["totalDiff"] for r in rows)
    O, PO = sum(r["old"] for r in rows), sum(r["old"] - r["oldDiff"] for r in rows)
    sign = lambda v: f"+{v:,}" if v > 0 else f"{v:,}"
    summary = [
        f"{label(ym)} 제주 1인 세대는 {T:,}세대로 지난달보다 {sign(T - PT)}세대({(T - PT) / PT * 100:+.1f}%) 바뀌었습니다.",
        f"80세 이상 1인 세대는 {O:,}세대로 지난달보다 {sign(O - PO)}세대입니다.",
        (f"기준을 넘은 동은 {len(flagged)}곳이며, 이달 먼저 살펴볼 동은 " + ", ".join(r["dong"] for r in top) + "입니다.")
        if top else "이달은 기준을 넘은 동이 없습니다.",
    ]
    return {"ym": ym, "label": label(ym), "prev": ym_shift(ym, -1), "hasYear": bool(year),
            "summary": summary, "top": [r["dong"] for r in top], "flaggedCount": len(flagged),
            "rules": RULES, "rows": sorted(rows, key=lambda r: r["dong"])}


def to_md(rep, sample):
    L = [f"# {rep['label']} 1인 세대 살핌 보고서", ""]
    if sample:
        L += ["> 교육용 가상 데이터로 만든 보고서입니다. 실제 주민등록 통계가 아닙니다.", ""]
    L += ["## 요약", ""] + [f"- {s}" for s in rep["summary"]] + [""]
    by = {r["dong"]: r for r in rep["rows"]}
    if rep["top"]:
        L += ["## 이달 먼저 살펴볼 동", "", "| 동 | 행정시 | 걸린 기준 | 80세 이상 (지난달 대비) | 80세 이상 비중 | 청년 (지난달 대비) |", "| --- | --- | --- | --- | --- | --- |"]
        for d in rep["top"]:
            r = by[d]
            L.append(f"| {d} | {r['city']} | {', '.join(r['hits'])} | {r['old']:,} ({r['oldDiff']:+,}) | {r['oldShare']}% | {r['young']:,} ({r['youngDiff']:+,}) |")
        L.append("")
    sections = [("80세 이상 한 달 증가", f"80세 이상 1인 세대가 지난달보다 {RULES['old_month_up']}세대 이상 늘어난 동", lambda r: f"{r['old']:,} ({r['oldDiff']:+,})"),
                ("청년 급증", f"청년(20~30대) 1인 세대가 지난달보다 {RULES['young_month_pct']}% 이상, {RULES['young_month_min']}세대 이상 늘어난 동", lambda r: f"{r['young']:,} ({r['youngDiff']:+,}, {r['youngPct']:+.1f}%)"),
                ("80세 이상 비중 높음", f"1인 세대 중 80세 이상 비중이 {RULES['old_share']}% 이상이고 지난달보다 {RULES['old_share_up']}%p 이상 오른 동", lambda r: f"{r['oldShare']}% ({r['oldShareDiff']:+.1f}%p)"),
                ("80세 이상 1년 증가", f"80세 이상 1인 세대가 작년 같은 달보다 {RULES['old_year_pct']}% 이상 늘어난 동", lambda r: f"{r['oldYearPct']:+.1f}%")]
    L += ["## 기준별 목록", ""]
    for name, desc, val in sections:
        hit = [r for r in rep["rows"] if name in r["hits"]]
        L += [f"### {name} ({len(hit)}곳)", "", desc, ""]
        L += [f"- {r['dong']} ({r['city']}): {val(r)}" for r in hit] or ["- 해당 없음"]
        L.append("")
    L += ["## 알고 쓸 점", "",
          "- 주민등록 1인 세대는 통계청 1인 가구와 기준이 다릅니다.",
          "- 통 · 반 값은 읍면동으로 합쳐서만 씁니다.",
          "- 살필 순서의 참고이며, 위기 가구를 찾아내는 근거가 아닙니다.",
          "- 요약 문장은 외부 AI 없이 계산한 숫자를 문장 틀에 넣어 만들었습니다.", "",
          "자료: 행정안전부_법정동별(행정동 통반단위) 성/연령별 주민등록 1인세대수 (공공데이터포털)"]
    return "\n".join(L) + "\n"


def main():
    data = json.load(open(DATA, encoding="utf-8"))
    try:
        old = json.load(open(OUT, encoding="utf-8"))
    except Exception:
        old = {}
    reps = {}
    for ym in sorted(data["months"]):
        r = build(data, ym)
        if r:
            reps[ym] = r
    out = {"sample": bool(data.get("sample")), "source": data.get("source"), "ages": data["ages"],
           "months": sorted(data["months"]), "reports": reps}
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    if not reps:
        print("비교할 지난달 자료가 아직 없어 보고서를 만들지 않았습니다.")
        return
    latest = max(reps)
    os.makedirs(MD_DIR, exist_ok=True)
    path = f"{MD_DIR}/{latest}.md"
    is_new = latest not in old.get("reports", {}) or not os.path.exists(path) or bool(old.get("sample")) != out["sample"]
    print(path, "보고서 작성 (새 달)" if is_new else "보고서 갱신")
    if is_new and os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"new_report={path}\nreport_title={reps[latest]['label']} 1인 세대 살핌 보고서\n")


if __name__ == "__main__":
    main()
