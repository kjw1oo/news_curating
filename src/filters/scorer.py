import json
import re
from src.models import NewsItem, Category

_PROMPTS = {
    Category.GLOBAL_AI: "AI 산업 판도를 바꿀 수준인지 0~10으로 평가. 신규 파운데이션 모델, 수십억 달러 M&A, 규제 판도 변화, 패러다임 전환 연구는 8.5+. 제품 업데이트·마케팅·루머는 3 이하.",
    Category.GLOBAL_FINANCE_AI: "금융 AI 실용화 관점에서 의미 있는지 0~10으로 평가. 실제 도입·운영 사례, 신규 AI 금융 서비스, 공식 AI 전략 발표는 7+. 단순 언급은 4 이하.",
    Category.DOMESTIC_FINANCE_AI: "국내 금융지주의 AI·데이터 활동으로서 가치 있는지 0~10으로 평가(누락 방지 우선, 넓게). 신규 서비스, AI 조직·채용·파트너십, 투자·예산 발표, 데이터 거버넌스/마이데이터는 4+. AI 단어만 있는 홍보성은 2 이하.",
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
        return {"score": float(d["score"]), "reason": str(d["reason"]), "send": bool(d["send"])}
    except (json.JSONDecodeError, KeyError, ValueError, TypeError):
        return None


def default_caller(item: NewsItem) -> str:
    """실제 Anthropic 호출. 단위 테스트에서는 fake로 대체된다."""
    import anthropic
    client = anthropic.Anthropic()
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001", max_tokens=300,
        messages=[{"role": "user", "content": build_prompt(item)}],
    )
    return resp.content[0].text


def score(items: list[NewsItem], caller=default_caller) -> list[NewsItem]:
    for it in items:
        parsed = parse_score_response(caller(it))
        if parsed is None:
            it.importance_score = None
            it.send_recommended = False
            continue
        it.importance_score = parsed["score"]
        it.importance_reason = parsed["reason"]
        it.send_recommended = parsed["send"]
    return items
