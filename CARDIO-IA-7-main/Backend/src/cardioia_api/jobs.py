import asyncio
import json
from contextlib import suppress

from .core import DomainError, job_output
from .database import now, pack, uid


class Jobs:
    def __init__(self, database, engine, timeout=180):
        self.db, self.engine, self.timeout = database, engine, timeout
        self.queue = asyncio.Queue(maxsize=10)
        self.pending = {}
        self.enqueued = set()
        self.worker = None

    def start(self):
        self.db.recover_jobs()
        self.worker = asyncio.create_task(self.run())

    async def close(self):
        if self.worker:
            self.worker.cancel()
            with suppress(asyncio.CancelledError):
                await self.worker
        self.db.recover_jobs()

    def submit(self, kind, case_id, owner, payload, measurement_id=None, revision=None,
               conversation_id=None, automatic=False):
        dedup = f"analysis:{measurement_id}:{revision}" if kind == "analysis" else None
        key = "analysis:" + case_id if kind == "analysis" and automatic else uid("task")
        with self.db.connect(write=True) as db:
            if dedup:
                previous = db.execute("SELECT * FROM jobs WHERE dedup_key=?", (dedup,)).fetchone()
                if previous and previous["status"] != "failed":
                    return job_output(previous)
            if key not in self.enqueued and self.queue.full():
                raise DomainError(429, "queue_full", "Fila cheia. Tente novamente mais tarde.")
            old_id = self.pending.get(key)
            if old_id:
                db.execute("UPDATE jobs SET status='failed',completed_at=?,error=? WHERE job_id=? AND status='queued'",
                           (now(), pack({"code": "superseded", "message": "Substituída por uma leitura mais recente."}), old_id))
            job_id = previous["job_id"] if dedup and previous else uid("ana" if kind == "analysis" else "msg")
            if dedup and previous:
                db.execute("UPDATE jobs SET status='queued',requested_at=?,completed_at=NULL,error=NULL,result=NULL,payload=? WHERE job_id=?",
                           (now(), pack(payload), job_id))
            else:
                db.execute("INSERT INTO jobs(job_id,kind,case_id,owner,conversation_id,measurement_id,revision,dedup_key,status,requested_at,payload) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                           (job_id, kind, case_id, owner, conversation_id, measurement_id, revision, dedup, "queued", now(), pack(payload)))
            row = db.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        self.pending[key] = job_id
        if key not in self.enqueued:
            self.enqueued.add(key)
            self.queue.put_nowait(key)
        return job_output(row)

    async def run(self):
        while True:
            key = await self.queue.get()
            self.enqueued.discard(key)
            job_id = self.pending.pop(key, None)
            try:
                if not job_id:
                    continue
                with self.db.connect(write=True) as db:
                    row = db.execute("SELECT rowid,* FROM jobs WHERE job_id=?", (job_id,)).fetchone()
                    if row["status"] != "queued":
                        continue
                    db.execute("UPDATE jobs SET status='running' WHERE job_id=?", (job_id,))
                payload = json.loads(row["payload"])
                if row["kind"] == "analysis":
                    operation = self.engine.analyze(payload["model_input"])
                else:
                    with self.db.connect() as db:
                        completed = db.execute("SELECT payload,result FROM jobs WHERE conversation_id=? AND status='completed' AND rowid<? ORDER BY rowid DESC LIMIT 4",
                                               (row["conversation_id"], row["rowid"])).fetchall()
                    history = []
                    for old in reversed(completed):
                        history.extend([{"role": "user", "content": json.loads(old["payload"])["text"]},
                                        {"role": "assistant", "content": json.loads(old["result"])["text"]}])
                    operation = self.engine.chat(payload["text"], history, payload["snapshot"])
                result = await asyncio.wait_for(operation, timeout=self.timeout)
                with self.db.connect(write=True) as db:
                    db.execute("UPDATE jobs SET status='completed',completed_at=?,result=? WHERE job_id=?", (now(), pack(result), job_id))
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                code = "timeout" if isinstance(exc, TimeoutError) else "engine_unavailable"
                with self.db.connect(write=True) as db:
                    db.execute("UPDATE jobs SET status='failed',completed_at=?,error=? WHERE job_id=?",
                               (now(), pack({"code": code, "message": "Não foi possível concluir a execução do motor local."}), job_id))
            finally:
                self.queue.task_done()
