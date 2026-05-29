from src.models import NewsItem


class Collector:
    category: str

    def collect(self) -> list[NewsItem]:
        raise NotImplementedError
