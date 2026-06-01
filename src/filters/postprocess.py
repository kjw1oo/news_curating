import re
from src.models import NewsItem

# 한글 조사(부착어) — 명사 뒤에 붙어 같은 단어를 다른 토큰으로 보이게 한다.
# dedup 토큰화에서 동일 이벤트 변형 제목("우리금융이/우리금융", "플랫폼을/플랫폼")이
# 갈라지지 않도록 토큰 말미 조사를 벗겨 표제어를 정규화한다(2글자→1글자 순으로 탐욕적).
# 한국어 뉴스(domestic_finance_ai)의 dedup FN을 줄이는 정밀도 보정.
_KO_JOSA = (
    "으로서", "으로써", "에서는", "에게서", "으로", "에서", "에게", "께서",
    "이라는", "라는", "라고", "이라고", "은", "는", "이", "가", "을", "를",
    "과", "와", "의", "에", "도", "만", "께", "랑", "이나", "나", "든",
)


def _strip_josa(token: str) -> str:
    """한글로 끝나는 토큰의 말미 조사를 1회 제거. 어근이 2글자 이상 남을 때만."""
    if not token or not ("가" <= token[-1] <= "힣"):
        return token
    for josa in _KO_JOSA:  # 긴 조사 우선
        if token.endswith(josa) and len(token) - len(josa) >= 2:
            return token[: -len(josa)]
    return token


def apply_threshold(items: list[NewsItem], thresholds: dict) -> list[NewsItem]:
    """카테고리별 임계값 미만이면 send_recommended를 False로 끈다."""
    for it in items:
        cutoff = thresholds.get(it.category, 5.0)
        if it.importance_score is None or it.importance_score < cutoff:
            it.send_recommended = False
    return items


def _norm_tokens(title: str) -> set[str]:
    cleaned = re.sub(r"[^0-9a-z가-힣 ]", " ", title.lower())
    return {_strip_josa(t) for t in cleaned.split() if len(t) > 1}


def _similar(a: set[str], b: set[str], threshold: float = 0.6) -> bool:
    if not a or not b:
        return False
    jaccard = len(a & b) / len(a | b)
    return jaccard >= threshold


# 제목 끝의 " - 매체명" 류 출처 접미(구글뉴스·언론사 표기) 제거 — 동일 기사 매칭률 향상.
_SRC_SUFFIX_RE = re.compile(r"\s*[-–—|]\s*[^-–—|]{1,22}$")
# 금융사 조직명 접사 — "NH농협은행/농협은행/농협" 토큰을 같은 어근("농협")으로 정규화.
_ORG_AFFIX = ("은행", "금융지주", "금융", "지주", "증권", "카드", "생명", "화재", "캐피탈", "뱅크", "bank")
# 같은 사건 판정에서 변별력 없는 흔한 토큰(이것만 겹치는 건 같은 사건 근거가 못 됨).
_EVENT_STOP = {"ai", "인공지능", "투자", "직접투자", "기업", "뉴스", "발표", "추진",
               "구축", "도입", "협력", "전환", "서비스", "신규", "출시"}
# 날짜 게이팅 엔티티-overlap 합치기를 적용할 카테고리(한국 금융 — 영어 과병합 방지).
_KO_FIN_CATS = {"woori", "domestic_finance_ai"}


def _org_norm(t: str) -> str:
    if t.startswith("nh") and len(t) > 3:
        t = t[2:]
    for s in _ORG_AFFIX:
        if t.endswith(s) and len(t) - len(s) >= 2:
            return t[: -len(s)]
    return t


def _event_tokens(title: str) -> set:
    return {_org_norm(t) for t in _norm_tokens(_SRC_SUFFIX_RE.sub("", title or ""))}


def _same_event(ta, tb, ca, cb, da, db, threshold) -> bool:
    if not ta or not tb:
        return False
    inter = ta & tb
    if len(inter) / len(ta | tb) >= threshold:   # 제목 유사도(전 카테고리, 안전)
        return True
    # 같은 날짜 + 한국 금융 + 변별 토큰 2개+ 공유 + 짧은쪽 50% 포함 → 같은 사건
    # (매체별 헤드라인이 크게 달라도 동일 이벤트를 묶는다. 영어 글로벌엔 미적용)
    if ca in _KO_FIN_CATS and cb in _KO_FIN_CATS and da and da == db:
        if len(inter - _EVENT_STOP) >= 2 and len(inter) / min(len(ta), len(tb)) >= 0.5:
            return True
    return False


def group_events(items: list[NewsItem], threshold: float = 0.45) -> list[list[NewsItem]]:
    """'같은 사건'을 전이적(연결요소)으로 그룹화 — 표시 합치기·중복 제거가 공유.

    엣지: ① 제목 토큰 유사도(jaccard≥threshold, 전 카테고리) ② 같은 날짜+한국금융+엔티티
    overlap. 전이적 묶음이라 헤드라인이 제각각인 한 사건(여러 매체 보도)도 완전히 합친다.
    """
    items = list(items)
    n = len(items)
    toks = [_event_tokens(it.title) for it in items]
    dts = [(it.published_at or "")[:10] for it in items]
    cats = [it.category for it in items]
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i in range(n):
        for j in range(i + 1, n):
            if find(i) != find(j) and _same_event(
                    toks[i], toks[j], cats[i], cats[j], dts[i], dts[j], threshold):
                parent[find(i)] = find(j)
    comp: dict = {}
    for i in range(n):
        comp.setdefault(find(i), []).append(items[i])
    return list(comp.values())


def _best_of(group: list[NewsItem]) -> NewsItem:
    """그룹 대표 = 발송추천 > 점수 > 최신 순으로 가장 대표적인 1건."""
    return max(group, key=lambda x: (
        1 if x.send_recommended else 0,
        x.importance_score if x.importance_score is not None else -1,
        x.published_at or "",
    ))


def duplicate_drop_ids(items: list[NewsItem], threshold: float = 0.45) -> list[str]:
    """중복 뉴스 그룹에서 최고 점수 1건만 남기고 제거할 나머지 id 리스트를 반환."""
    drop = []
    for g in group_events(items, threshold):
        if len(g) <= 1:
            continue
        best = _best_of(g)
        drop += [it.id for it in g if it.id != best.id]
    return drop


def group_similar(items: list[NewsItem], threshold: float = 0.6) -> list[list[NewsItem]]:
    """유사 제목끼리 묶은 그룹 리스트를 반환(greedy first-match, 입력 순서 의존).

    같은 이벤트의 변형 제목을 한 그룹으로 묶는다. dedup·배치 채점·표시 합치기가 공유한다.
    threshold를 낮추면(예: 0.5) 매체별 헤드라인 변형까지 더 적극적으로 묶는다.
    """
    groups: list[list[NewsItem]] = []
    reps: list[set[str]] = []  # 각 그룹 대표 제목의 토큰(재계산 방지)
    for it in items:
        tokens = _norm_tokens(it.title)
        for gi, rep in enumerate(reps):
            if _similar(tokens, rep, threshold):
                groups[gi].append(it)
                break
        else:
            groups.append([it])
            reps.append(tokens)
    return groups


def dedup(items: list[NewsItem]) -> list[NewsItem]:
    """유사 제목을 같은 dedup_group으로 묶고, 그룹 내 점수 최고 1건만 send_recommended 유지."""
    groups = group_similar(items)
    for gi, g in enumerate(groups):
        gid = f"g{gi}"
        winner = max(g, key=lambda x: (x.send_recommended, x.importance_score or -1))
        for it in g:
            it.dedup_group = gid
            if it is not winner:
                it.send_recommended = False
    return items
