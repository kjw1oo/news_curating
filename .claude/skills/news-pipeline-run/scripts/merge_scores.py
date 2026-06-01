"""data/_scores_*.json(에이전트별 채점)을 data/_scores.json으로 병합 + 커버리지 검증.

각 점수 항목을 {score(0~10 float), reason, send(bool)}로 정규화하고, export된 대표 id에
속한 것만 남긴다. 누락 id가 있으면 출력해 재채점 대상을 알려준다.
"""
import json
from pathlib import Path

ids = {x["id"] for x in json.load(open("data/_unscored.json", encoding="utf-8"))}
merged = {}
for p in sorted(Path("data").glob("_scores_*.json")):
    try:
        merged.update(json.loads(p.read_text(encoding="utf-8")))
    except Exception as e:
        print("PARSE ERR", p.name, e)

clean = {}
for k, v in merged.items():
    if k not in ids or not isinstance(v, dict):
        continue
    try:
        clean[k] = {"score": float(v["score"]),
                    "reason": str(v.get("reason", "")),
                    "send": bool(v.get("send", False))}
    except (KeyError, ValueError, TypeError):
        pass

Path("data/_scores.json").write_text(json.dumps(clean, ensure_ascii=False), encoding="utf-8")
missing = ids - set(clean)
print(f"채점 커버 {len(clean)} / 대표 {len(ids)} / 누락 {len(missing)}")
if missing:
    print("누락 id(재채점 필요):", list(missing)[:10])
