"""테스트는 항상 로컬 sqlite(임시 파일)로 실행한다.

.env에 TURSO 설정이 있어도 storage._load_dotenv가 로드하지 않도록 막고(_DOTENV_LOADED),
TURSO 환경변수를 제거해 Storage가 sqlite 경로를 쓰게 한다. (테스트가 실DB를 건드리지 않게)
"""
import os

os.environ["_DOTENV_LOADED"] = "1"
os.environ.pop("TURSO_DATABASE_URL", None)
os.environ.pop("TURSO_AUTH_TOKEN", None)
