"""Vercel 서버리스 엔트리 — 대시보드 + 읽기 API.

데이터는 로컬 배치 파이프라인(수집·채점)이 Turso(libSQL)에 기록하고, 여기서는 읽어서
보여주기만 한다. 따라서 수집/발송 같은 쓰기 액션은 클라우드에서 비활성화한다.

필요 환경변수(Vercel 프로젝트 설정):
  - TURSO_DATABASE_URL  (libsql://... )
  - TURSO_AUTH_TOKEN
없으면 로컬 sqlite로 폴백(로컬 테스트용).
"""
import sys
import yaml
from pathlib import Path

# 레포 루트를 import 경로에 추가(api/ 하위에서 src 패키지 접근).
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from src.storage import Storage
from src.api.app import create_app

CONFIG = yaml.safe_load((_ROOT / "config.yaml").read_text(encoding="utf-8"))
STORAGE = Storage()  # TURSO_DATABASE_URL 있으면 libSQL, 없으면 data/news.db


def _collect_disabled():
    return {"status": "disabled",
            "message": "수집은 로컬 배치 파이프라인에서 실행됩니다(클라우드는 표시 전용).",
            "collected": 0, "stored": 0, "recommended": 0}


# Vercel @vercel/python은 ASGI `app`을 감지해 서빙한다.
app = create_app(storage=STORAGE, config=CONFIG, run_collect=_collect_disabled)
