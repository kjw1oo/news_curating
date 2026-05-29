from src.filters.scorer import parse_score_response, score
from src.models import NewsItem, Category, make_id


def _item():
    return NewsItem(id=make_id("u1"), category=Category.DOMESTIC_FINANCE_AI, title="우리금융 AI 플랫폼",
                    url="u1", source="s", published_at="", collected_at="", summary_raw="생성형 AI 도입")


def test_parse_score_response_extracts_fields():
    raw = '여기 결과입니다: {"score": 6.5, "reason": "전 계열사 확대로 의미 있음", "send": true}'
    parsed = parse_score_response(raw)
    assert parsed == {"score": 6.5, "reason": "전 계열사 확대로 의미 있음", "send": True}


def test_parse_score_response_handles_garbage():
    assert parse_score_response("모델이 JSON을 안 줌") is None


def test_score_fills_fields_using_injected_caller():
    def fake_caller(item):
        return '{"score": 7.2, "reason": "근거", "send": true}'
    out = score([_item()], caller=fake_caller)
    assert out[0].importance_score == 7.2
    assert out[0].importance_reason == "근거"
    assert out[0].send_recommended is True


def test_score_on_failure_leaves_item_unscored():
    def bad_caller(item):
        return "잘못된 응답"
    out = score([_item()], caller=bad_caller)
    assert out[0].importance_score is None
    assert out[0].send_recommended is False
