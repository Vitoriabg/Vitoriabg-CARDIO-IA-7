import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4

from .config import ROOT
from .security import PASSWORDS, digest


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def uid(prefix):
    return prefix + "-" + uuid4().hex


def pack(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


class Database:
    def __init__(self, path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS users(username TEXT PRIMARY KEY, password_hash TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS cases(case_id TEXT PRIMARY KEY, owner TEXT NOT NULL REFERENCES users(username),
                title TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1, latest_id TEXT);
            CREATE TABLE IF NOT EXISTS contexts(case_id TEXT NOT NULL REFERENCES cases(case_id), revision INTEGER NOT NULL,
                data TEXT NOT NULL, PRIMARY KEY(case_id,revision));
            CREATE TABLE IF NOT EXISTS devices(device_id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(case_id),
                token_hash TEXT UNIQUE NOT NULL, active_boot TEXT);
            CREATE TABLE IF NOT EXISTS boots(device_id TEXT NOT NULL, boot_id TEXT NOT NULL, closed INTEGER NOT NULL,
                PRIMARY KEY(device_id,boot_id));
            CREATE TABLE IF NOT EXISTS measurements(measurement_id TEXT PRIMARY KEY, case_id TEXT NOT NULL,
                device_id TEXT NOT NULL, boot_id TEXT NOT NULL, sequence INTEGER NOT NULL,
                received_at TEXT NOT NULL, data TEXT NOT NULL,
                UNIQUE(device_id,boot_id,sequence));
            CREATE INDEX IF NOT EXISTS measurements_case ON measurements(case_id, received_at);
            """)
            db.executescript("""
            CREATE TABLE IF NOT EXISTS predictions(measurement_id TEXT NOT NULL, revision INTEGER NOT NULL,
                data TEXT NOT NULL, PRIMARY KEY(measurement_id,revision));
            CREATE TABLE IF NOT EXISTS conversations(conversation_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, owner TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS jobs(job_id TEXT PRIMARY KEY, kind TEXT NOT NULL, case_id TEXT NOT NULL,
                owner TEXT NOT NULL, conversation_id TEXT, measurement_id TEXT, revision INTEGER,
                dedup_key TEXT UNIQUE, status TEXT NOT NULL, requested_at TEXT NOT NULL, completed_at TEXT,
                payload TEXT NOT NULL, result TEXT, error TEXT);
            CREATE INDEX IF NOT EXISTS jobs_case ON jobs(case_id, requested_at);
            """)

    @contextmanager
    def connect(self, write=False):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            if write:
                db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def seed(self, settings):
        with self.connect(write=True) as db:
            exists = db.execute("SELECT 1 FROM users WHERE username=?", (settings.username,)).fetchone()
            if not exists:
                db.execute("INSERT INTO users VALUES (?,?)", (settings.username, PASSWORDS.hash(settings.demo_password)))
            db.execute("INSERT OR IGNORE INTO cases(case_id,owner,title) VALUES ('caso-demo-01',?, 'Caso sintético de demonstração')", (settings.username,))
            demo = json.loads((ROOT / "data/exemplos/novo_caso.json").read_text())
            context = {key: value for key, value in demo.items() if key not in {"temperatura", "fc_media"}}
            db.execute("INSERT OR IGNORE INTO contexts VALUES ('caso-demo-01',1,?)", (pack(context),))
            db.execute("INSERT OR IGNORE INTO devices(device_id,case_id,token_hash) VALUES ('esp32-demo-01','caso-demo-01',?)", (digest(settings.device_token),))

    def recover_jobs(self):
        with self.connect(write=True) as db:
            db.execute("UPDATE jobs SET status='failed',completed_at=?,error=? WHERE status IN ('running','queued')",
                       (now(), pack({"code": "server_restarted", "message": "Processamento interrompido; envie outra solicitação."})))
