import hashlib
import dataclasses
from dataclasses import dataclass, asdict
from urllib.parse import urlsplit, urlunsplit


class Category:
    GLOBAL_AI = "global_ai"
    GLOBAL_FINANCE_AI = "global_finance_ai"
    DOMESTIC_FINANCE_AI = "domestic_finance_ai"
    ALL = (GLOBAL_AI, GLOBAL_FINANCE_AI, DOMESTIC_FINANCE_AI)


LABELS = {
    Category.GLOBAL_AI: "글로벌 AI",
    Category.GLOBAL_FINANCE_AI: "글로벌 금융 AI",
    Category.DOMESTIC_FINANCE_AI: "국내 금융 AI",
}


def make_id(url: str) -> str:
    parts = urlsplit(url.strip().lower())
    normalized = urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


@dataclass
class NewsItem:
    id: str
    category: str
    title: str
    url: str
    source: str
    published_at: str
    collected_at: str
    summary_raw: str
    keyword_passed: bool = False
    importance_score: float | None = None
    importance_reason: str = ""
    send_recommended: bool = False
    dedup_group: str | None = None
    sent: bool = False
    sent_at: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "NewsItem":
        missing = [
            k for k, f in cls.__dataclass_fields__.items()
            if k not in d
            and f.default is dataclasses.MISSING
            and f.default_factory is dataclasses.MISSING
        ]
        if missing:
            raise ValueError(f"Missing required fields: {missing}")
        return cls(**{k: d.get(k) for k in cls.__dataclass_fields__})
