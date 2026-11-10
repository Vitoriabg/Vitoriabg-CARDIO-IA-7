import asyncio
import json
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager

import jwt
from fastapi import Depends, FastAPI, File, Header, Query, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.exceptions import HTTPException

from .config import Settings
from .core import Core, DomainError, job_output
from .database import Database, now, pack, uid
from .engine import Engine
from .jobs import Jobs
from .schemas import AnalysisRequest, ContextUpdate, ConversationRequest, Login, MessageRequest, Telemetry
from .security import PASSWORDS, digest, issue_token, read_token


class BodyLimit:
    def __init__(self, app, maximum):
        self.app, self.maximum = app, maximum

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        parts, size = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            parts.append(message)
            size += len(message.get("body", b""))
            if size > self.maximum:
                response = JSONResponse({"error": {"code": "body_too_large", "message": "Requisição muito grande.", "request_id": uid("req")}}, status_code=413)
                return await response(scope, receive, send)
            if not message.get("more_body", False):
                break
        async def replay():
            if parts:
                return parts.pop(0)
            return await receive()
        return await self.app(scope, replay, send)


class RateLimits:
    def __init__(self):
        self.values = defaultdict(deque)

    def check(self, category, subject, limit):
        timestamp = time.monotonic()
        if len(self.values) > 10000:
            for key in list(self.values):
                if not self.values[key] or self.values[key][-1] < timestamp - 60:
                    self.values.pop(key, None)
        entries = self.values[(category, subject)]
        while entries and entries[0] <= timestamp - 60:
            entries.popleft()
        if len(entries) >= limit:
            raise DomainError(429, "rate_limited", "Limite de requisições excedido.")
        entries.append(timestamp)


def create_app(settings=None, engine=None):
    settings = settings or Settings.from_env()
    engine = engine or Engine()
    database = Database(settings.database)
    database.seed(settings)
    core, jobs, rates = Core(database, engine), Jobs(database, engine, settings.job_timeout), RateLimits()
    dummy_hash = PASSWORDS.hash("invalid-password-for-timing")

    @asynccontextmanager
    async def lifespan(app):
        jobs.start()
        yield
        await jobs.close()

    app = FastAPI(title="CardioIA", version="0.1.0", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings, app.state.db, app.state.core, app.state.jobs = settings, database, core, jobs
    app.add_middleware(BodyLimit, maximum=settings.max_body)
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.allowed_origins),
                       allow_methods=["GET", "POST", "PUT"], allow_headers=["Authorization", "Content-Type", "X-Device-Token"])

    @app.middleware("http")
    async def request_headers(request, call_next):
        request.state.request_id = uid("req")
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response

    def error_response(request, status, code, message):
        return JSONResponse({"error": {"code": code, "message": message, "request_id": getattr(request.state, "request_id", uid("req"))}}, status_code=status)

    @app.exception_handler(DomainError)
    async def domain_error(request, exc):
        return error_response(request, exc.status, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return error_response(request, 422, "invalid_payload", "Dados inválidos ou campos não permitidos.")

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return error_response(request, exc.status_code, "http_error", "Requisição não aceita.")

    @app.exception_handler(Exception)
    async def unexpected_error(request, exc):
        return error_response(request, 500, "internal_error", "Não foi possível concluir a requisição.")

    bearer = HTTPBearer(auto_error=False)

    def user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        if credentials is None:
            raise DomainError(401, "unauthorized", "Sessão ausente ou inválida.")
        try:
            username = read_token(credentials.credentials, settings)
        except (jwt.PyJWTError, TypeError, KeyError):
            raise DomainError(401, "unauthorized", "Sessão ausente ou inválida.")
        with database.connect() as db:
            if not db.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
                raise DomainError(401, "unauthorized", "Sessão ausente ou inválida.")
        rates.check("read", username, 60)
        return username

    def device(x_device_token: str | None = Header(default=None)):
        if not x_device_token or len(x_device_token) > 256:
            raise DomainError(401, "unauthorized_device", "Dispositivo não autorizado.")
        with database.connect() as db:
            row = db.execute("SELECT * FROM devices WHERE token_hash=?", (digest(x_device_token),)).fetchone()
        if row is None:
            raise DomainError(401, "unauthorized_device", "Dispositivo não autorizado.")
        rates.check("telemetry", row["device_id"], 30)
        return row

    def auto_analysis(case_id, username):
        if not settings.automatic_analysis:
            return
        dashboard = core.dashboard(case_id, username)
        prediction = dashboard["prediction"]
        if prediction and prediction["status"] == "ready":
            try:
                values = core.analysis_input(case_id, username, prediction["measurement_id"], prediction["context_revision"])
                jobs.submit("analysis", case_id, username, {"model_input": values}, prediction["measurement_id"], prediction["context_revision"], automatic=True)
            except DomainError as exc:
                if exc.code != "queue_full":
                    raise

    @app.get("/health")
    @app.get("/api/v1/health")
    def health():
        return {"status": "ok"}

    @app.post("/api/v1/auth/login")
    async def login(payload: Login, request: Request):
        rates.check("login", request.client.host if request.client else "unknown", 10)
        with database.connect() as db:
            row = db.execute("SELECT password_hash FROM users WHERE username=?", (payload.username,)).fetchone()
        valid = await asyncio.to_thread(PASSWORDS.verify, payload.password, row["password_hash"] if row else dummy_hash)
        if not valid or row is None:
            raise DomainError(401, "invalid_credentials", "Usuário ou senha inválidos.")
        return {"access_token": issue_token(payload.username, settings), "token_type": "bearer", "expires_in": settings.token_ttl}

    @app.get("/api/v1/openapi.json")
    def schema(username=Depends(user)):
        return app.openapi()

    @app.get("/api/v1/cases")
    def cases(limit: int = Query(20, ge=1, le=100), cursor: str = "", username=Depends(user)):
        with database.connect() as db:
            rows = db.execute("SELECT case_id,title FROM cases WHERE owner=? AND case_id>? ORDER BY case_id LIMIT ?", (username, cursor, limit + 1)).fetchall()
        return {"items": [dict(row) for row in rows[:limit]], "next_cursor": rows[limit - 1]["case_id"] if len(rows) > limit else None}

    @app.get("/api/v1/cases/{case_id}/context")
    def context(case_id: str, username=Depends(user)):
        return core.context(case_id, username)

    @app.put("/api/v1/cases/{case_id}/context")
    async def change_context(case_id: str, payload: ContextUpdate, username=Depends(user)):
        value = core.update_context(case_id, username, payload)
        auto_analysis(case_id, username)
        return value

    @app.post("/api/v1/telemetry", status_code=201)
    async def telemetry(payload: Telemetry, response: Response, registered=Depends(device)):
        if payload.device_id != registered["device_id"]:
            raise DomainError(403, "device_mismatch", "Dispositivo não corresponde ao token.")
        value, updated = core.telemetry(payload, registered)
        if value["duplicate"]:
            response.status_code = 200
        if updated:
            with database.connect() as db:
                owner = db.execute("SELECT owner FROM cases WHERE case_id=?", (registered["case_id"],)).fetchone()["owner"]
            auto_analysis(registered["case_id"], owner)
        return value

    @app.get("/api/v1/cases/{case_id}/dashboard")
    def dashboard(case_id: str, username=Depends(user)):
        return core.dashboard(case_id, username)

    @app.get("/api/v1/cases/{case_id}/measurements")
    def measurements(case_id: str, limit: int = Query(20, ge=1, le=100), cursor: int | None = Query(None, ge=1), username=Depends(user)):
        with database.connect() as db:
            core.case(db, case_id, username)
            rows = db.execute("SELECT rowid,* FROM measurements WHERE case_id=? AND rowid<? ORDER BY rowid DESC LIMIT ?", (case_id, cursor or 9223372036854775807, limit + 1)).fetchall()
        return {"items": [{"measurement_id": row["measurement_id"], "received_at": row["received_at"], **json.loads(row["data"])} for row in rows[:limit]],
                "next_cursor": str(rows[limit - 1]["rowid"]) if len(rows) > limit else None}

    @app.post("/api/v1/cases/{case_id}/analyses", status_code=202)
    async def analyze(case_id: str, payload: AnalysisRequest, username=Depends(user)):
        rates.check("llm", username, 2)
        values = core.analysis_input(case_id, username, payload.measurement_id, payload.context_revision)
        return jobs.submit("analysis", case_id, username, {"model_input": values}, payload.measurement_id, payload.context_revision)

    @app.get("/api/v1/analyses/{analysis_id}")
    def analysis(analysis_id: str, username=Depends(user)):
        with database.connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE job_id=? AND owner=? AND kind='analysis'", (analysis_id, username)).fetchone()
        if not row:
            raise DomainError(404, "not_found", "Análise não encontrada.")
        return job_output(row)

    @app.post("/api/v1/conversations", status_code=201)
    def conversation(payload: ConversationRequest, username=Depends(user)):
        with database.connect(write=True) as db:
            core.case(db, payload.case_id, username)
            conversation_id = uid("conv")
            db.execute("INSERT INTO conversations VALUES (?,?,?)", (conversation_id, payload.case_id, username))
        return {"conversation_id": conversation_id}

    @app.post("/api/v1/conversations/{conversation_id}/messages", status_code=202)
    async def message(conversation_id: str, payload: MessageRequest, username=Depends(user)):
        rates.check("llm", username, 2)
        with database.connect() as db:
            row = db.execute("SELECT * FROM conversations WHERE conversation_id=? AND owner=?", (conversation_id, username)).fetchone()
        if row is None:
            raise DomainError(404, "not_found", "Conversa não encontrada.")
        snapshot = core.dashboard(row["case_id"], username)
        return jobs.submit("message", row["case_id"], username, {"text": payload.text, "snapshot": snapshot}, conversation_id=conversation_id)

    @app.get("/api/v1/conversations/{conversation_id}/messages/{message_id}")
    def message_result(conversation_id: str, message_id: str, username=Depends(user)):
        with database.connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE job_id=? AND conversation_id=? AND owner=? AND kind='message'", (message_id, conversation_id, username)).fetchone()
        if row is None:
            raise DomainError(404, "not_found", "Mensagem não encontrada.")
        return job_output(row)

    @app.post("/api/v1/text-triage")
    async def triage(payload: MessageRequest, username=Depends(user)):
        return await asyncio.to_thread(engine.triage, payload.text)

    @app.post("/api/v1/image-classifications")
    async def image(image: UploadFile = File(...), username=Depends(user)):
        if image.content_type not in {"image/png", "image/jpeg"}:
            raise DomainError(415, "unsupported_image", "Formato de imagem não aceito.")
        content = await image.read(5 * 1024 * 1024 + 1)
        if len(content) > 5 * 1024 * 1024:
            raise DomainError(413, "image_too_large", "Imagem excede 5 MB.")
        try:
            return await asyncio.to_thread(engine.classify_image, content)
        except (ValueError, ImportError, OSError):
            raise DomainError(503, "image_model_unavailable", "Classificador de imagens indisponível; artefato ou configuração pendente.")

    return app
