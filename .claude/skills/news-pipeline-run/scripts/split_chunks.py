"""data/_unscored.json을 N개 청크로 분할(병렬 채점 에이전트용).

사용: python <이 스크립트> [N]   (기본 N=6)
출력: data/_chunk_0.json .. data/_chunk_{N-1}.json
"""
import json
import math
import sys
from pathlib import Path

N = int(sys.argv[1]) if len(sys.argv) > 1 else 6
data = json.load(open("data/_unscored.json", encoding="utf-8"))
if not data:
    print("미채점 0건 — 채점할 것 없음")
    raise SystemExit(0)

size = max(1, math.ceil(len(data) / N))
made = 0
for i in range(N):
    chunk = data[i * size:(i + 1) * size]
    if not chunk:
        continue
    Path(f"data/_chunk_{i}.json").write_text(
        json.dumps(chunk, ensure_ascii=False, indent=2), encoding="utf-8")
    made += 1
print(f"대표 {len(data)}건 → {made}청크 (data/_chunk_0..{made - 1}.json)")
