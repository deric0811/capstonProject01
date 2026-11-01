"""환경 설정. 값은 .env 또는 환경변수에서 읽고, 비밀값은 출력하지 않는다."""
import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv(path):
    env = {}
    if path.exists():
        for line in path.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip("\"'")
    return env


@dataclass(frozen=True)
class Settings:
    kamis_api_key: str = field(repr=False)
    kamis_cert_id: str = field(repr=False)
    database_url: str = field(repr=False)
    kamis_url: str = "https://www.kamis.or.kr/service/price/xml.do"

    @property
    def secrets(self):
        return [s for s in (self.kamis_api_key, self.kamis_cert_id) if s]


def load_settings(env_file=ROOT / ".env"):
    env = {**_load_dotenv(env_file), **os.environ}
    return Settings(
        kamis_api_key=env.get("KAMIS_API_KEY", ""),
        kamis_cert_id=env.get("KAMIS_CERT_ID", ""),
        database_url=env.get("DATABASE_URL", "postgresql://tomato:tomato@localhost:5432/tomato"),
        kamis_url=env.get("KAMIS_URL", Settings.kamis_url),
    )


def mask(text, secrets):
    for s in secrets:
        text = text.replace(s, "***")
    return text
