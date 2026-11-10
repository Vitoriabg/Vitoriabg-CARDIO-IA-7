import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    database: Path
    jwt_secret: str = field(repr=False)
    demo_password: str = field(repr=False)
    device_token: str = field(repr=False)
    username: str = "demo"
    token_ttl: int = 3600
    allowed_origins: tuple[str, ...] = ("http://localhost:5173",)
    automatic_analysis: bool = True
    job_timeout: float = 180
    max_body: int = 6 * 1024 * 1024
    host: str = "127.0.0.1"
    port: int = 8000

    def __post_init__(self):
        if len(self.jwt_secret) < 32 or len(self.demo_password) < 12 or len(self.device_token) < 32:
            raise ValueError("Configure segredos locais válidos com python scripts/init_local.py.")
        if not 60 <= self.token_ttl <= 3600:
            raise ValueError("A duração da sessão deve ficar entre 60 e 3600 segundos.")
        if "*" in self.allowed_origins:
            raise ValueError("Configure origens CORS explícitas.")

    @classmethod
    def from_env(cls):
        load_dotenv(ROOT.parent / ".env", override=False)
        raw_path = Path(os.getenv("CARDIOIA_DATABASE_PATH", "storage/cardioia.sqlite3"))
        return cls(
            database=raw_path if raw_path.is_absolute() else ROOT / raw_path,
            jwt_secret=os.getenv("CARDIOIA_JWT_SECRET", ""),
            demo_password=os.getenv("CARDIOIA_DEMO_PASSWORD", ""),
            device_token=os.getenv("CARDIOIA_DEVICE_TOKEN", ""),
            username=os.getenv("CARDIOIA_DEMO_USERNAME", "demo"),
            token_ttl=int(os.getenv("CARDIOIA_TOKEN_TTL_SECONDS", "3600")),
            allowed_origins=tuple(x.strip() for x in os.getenv("CARDIOIA_ALLOWED_ORIGINS", "http://localhost:5173").split(",") if x.strip()),
            automatic_analysis=os.getenv("CARDIOIA_AUTO_ANALYSIS", "true").lower() == "true",
            host=os.getenv("CARDIOIA_API_HOST", "127.0.0.1"),
            port=int(os.getenv("PORT", os.getenv("CARDIOIA_API_PORT", "8000"))),
        )
