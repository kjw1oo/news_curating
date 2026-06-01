import json
import re
from src.models import NewsItem, Category

_PROMPTS = {
    Category.GLOBAL_AI: "AI 산업 '판도 전환'급 사건만 골라내라(빈도 최소화·아주 엄격). 9.5+는 오직: 선도 연구소의 신규 프런티어 파운데이션 모델 공개, 100억 달러+ 규모 M&A/투자, 업계를 바꾸는 규제·법안 확정, 새 아키텍처급 패러다임 전환 연구만. 그 외 제품 업데이트·점진적 연구·벤치마크·파트너십·소규모 펀딩·전망/오피니언·인물 동정은 모두 6 이하. 마케팅·루머·요약기사는 2 이하. 애매하면 낮게.",
    Category.GLOBAL_FINANCE_AI: "금융권을 실제로 흔드는 'AI 사건'만 골라내라(빈도 최소화·아주 엄격). 9+는 오직: 대형 금융기관의 대규모 공식 AI 전략·전사 도입, 시장 구조를 바꾸는 AI 적용, 금융 AI 관련 중대한 규제 확정만. 일상적 도입·파일럿·벤더 발표·단순 언급·실적 코멘트는 5 이하. 마케팅·홍보성은 2 이하. 애매하면 낮게.",
    Category.DOMESTIC_FINANCE_AI: "국내 금융지주의 AI·데이터 활동으로서 가치 있는지 0~10으로 평가(누락 방지 우선, 넓게). 신규 서비스, AI 조직·채용·파트너십, 투자·예산 발표, 데이터 거버넌스/마이데이터는 4+. AI 단어만 있는 홍보성은 2 이하.",
    Category.WOORI: "우리금융그룹(우리금융지주·우리은행·우리카드·우리종합금융 등 계열사)의 AI·데이터 활동으로서 가치 있는지 0~10으로 평가(누락 방지 우선, 넓게). 신규 AI 서비스·플랫폼, AI 조직·채용·파트너십, 투자·예산 발표, 데이터 거버넌스/마이데이터/디지털 전환은 4+. 단순 실적·점포·이벤트 등 AI/데이터 무관 기사나 홍보성은 2 이하.",
}


def build_prompt(item: NewsItem) -> str:
    criteria = _PROMPTS.get(item.category, _PROMPTS[Category.DOMESTIC_FINANCE_AI])
    return (
        f"{criteria}\n\n"
        f"제목: {item.title}\n출처: {item.source}\n발행: {item.published_at}\n본문요약: {item.summary_raw}\n\n"
        '오직 JSON만 출력: {"score": 0.0~10.0, "reason": "1~2문장", "send": true/false}'
    )


def parse_score_response(raw: str) -> dict | None:
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
        score_val = max(0.0, min(10.0, float(d["score"])))
        return {"score": score_val, "reason": str(d["reason"]), "send": bool(d["send"])}
    except (json.JSONDecodeError, KeyError, ValueError, TypeError):
        return None


def default_caller(item: NewsItem) -> str:
    """실제 Anthropic 호출. 단위 테스트에서는 fake로 대체된다.

    키가 없으면 즉시 실패시킨다 — SDK는 키 부재 시에도 ~60초 후에야 인증 에러를
    내므로, 키 없는 환경에서 수집이 항목마다 멈추는 것을 막는다(→ 미채점 저장 후
    news-batch-scoring으로 채점). 키가 있으면 짧은 타임아웃·1회 재시도로 호출한다.
    """
    import os
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY 미설정 — 실시간 채점 불가. news-batch-scoring 스킬을 사용하세요.")
    import anthropic
    client = anthropic.Anthropic(timeout=20.0, max_retries=1)
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001", max_tokens=300,
        messages=[{"role": "user", "content": build_prompt(item)}],
    )
    return resp.content[0].text


def score(items: list[NewsItem], caller=default_caller) -> list[NewsItem]:
    for it in items:
        try:
            raw = caller(it)
        except Exception:
            raw = None
        parsed = parse_score_response(raw) if raw is not None else None
        if parsed is None:
            it.importance_score = None
            it.send_recommended = False
            continue
        it.importance_score = parsed["score"]
        it.importance_reason = parsed["reason"]
        it.send_recommended = parsed["send"]
    return items
