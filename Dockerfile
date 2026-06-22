# AI 뉴스 모니터링 대시보드 — FastAPI 서버 컨테이너.
# 데이터는 Turso(libSQL)에서 읽는다(env: TURSO_DATABASE_URL / TURSO_AUTH_TOKEN).
# 두 변수가 없으면 컨테이너 내부 sqlite(data/news.db)로 폴백한다.
#
#   docker build -t news-curating .
#   docker run -p 8000:8000 \
#     -e TURSO_DATABASE_URL=libsql://<db>.turso.io \
#     -e TURSO_AUTH_TOKEN=<token> news-curating
#
# 참고: 수집·채점 배치는 컨테이너 밖(로컬 작업 스케줄러 + 에이전트)에서 돌고,
#       이 컨테이너는 Turso의 결과를 읽어 대시보드를 서빙하는 표시 계층이다.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONIOENCODING=utf-8

WORKDIR /app

# 의존성 먼저 설치(레이어 캐시 활용)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 앱 소스(서버 구동에 필요한 것만)
COPY src/ ./src/
COPY api/ ./api/
COPY run.py config.yaml ./

EXPOSE 8000

# 대시보드 + API 서버. 컨테이너 외부 접근을 위해 0.0.0.0 바인딩.
CMD ["uvicorn", "run:app", "--host", "0.0.0.0", "--port", "8000"]
