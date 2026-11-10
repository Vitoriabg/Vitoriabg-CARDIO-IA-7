import json
from datetime import datetime, timedelta, timezone

from .database import now, pack, uid


class DomainError(Exception):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message


class Core:
    def __init__(self, database, engine):
        self.db, self.engine = database, engine

    def case(self, db, case_id, owner):
        row = db.execute("SELECT * FROM cases WHERE case_id=? AND owner=?", (case_id, owner)).fetchone()
        if row is None:
            raise DomainError(404, "not_found", "Caso não encontrado.")
        return row

    def context(self, case_id, owner):
        with self.db.connect() as db:
            row = self.case(db, case_id, owner)
            values = db.execute("SELECT data FROM contexts WHERE case_id=? AND revision=?", (case_id, row["revision"])).fetchone()
            return {"schema_version": 1, "source": "synthetic", "context_revision": row["revision"], "values": json.loads(values["data"])}

    def update_context(self, case_id, owner, payload):
        with self.db.connect(write=True) as db:
            row = self.case(db, case_id, owner)
            if row["revision"] != payload.expected_revision:
                raise DomainError(409, "revision_conflict", "O contexto já foi atualizado.")
            revision = row["revision"] + 1
            db.execute("INSERT INTO contexts VALUES (?,?,?)", (case_id, revision, pack(payload.values.model_dump())))
            db.execute("UPDATE cases SET revision=? WHERE case_id=?", (revision, case_id))
            if row["latest_id"]:
                self.prediction(db, row["latest_id"], revision)
        return self.context(case_id, owner)

    def telemetry(self, payload, device):
        data = payload.model_dump()
        with self.db.connect(write=True) as db:
            existing = db.execute("SELECT * FROM measurements WHERE device_id=? AND boot_id=? AND sequence=?",
                                  (payload.device_id, payload.boot_id, payload.sequence)).fetchone()
            if existing:
                if existing["data"] != pack(data):
                    raise DomainError(409, "duplicate_conflict", "Sequência já recebida com conteúdo diferente.")
                return {"measurement_id": existing["measurement_id"], "received_at": existing["received_at"], "duplicate": True}, False
            boot = db.execute("SELECT * FROM boots WHERE device_id=? AND boot_id=?", (payload.device_id, payload.boot_id)).fetchone()
            if boot is None:
                if payload.historical:
                    db.execute("INSERT INTO boots VALUES (?,?,1)", (payload.device_id, payload.boot_id))
                else:
                    if payload.sequence > 1:
                        raise DomainError(409, "boot_not_started", "Nova inicialização deve começar na sequência 0 ou 1.")
                    db.execute("UPDATE boots SET closed=1 WHERE device_id=?", (payload.device_id,))
                    db.execute("INSERT INTO boots VALUES (?,?,0)", (payload.device_id, payload.boot_id))
                    db.execute("UPDATE devices SET active_boot=? WHERE device_id=?", (payload.boot_id, payload.device_id))
            device_now = db.execute("SELECT * FROM devices WHERE device_id=?", (payload.device_id,)).fetchone()
            measurement_id, received_at = uid("med"), now()
            db.execute("INSERT INTO measurements VALUES (?,?,?,?,?,?,?)", (measurement_id, device["case_id"], payload.device_id,
                       payload.boot_id, payload.sequence, received_at, pack(data)))
            case = db.execute("SELECT * FROM cases WHERE case_id=?", (device["case_id"],)).fetchone()
            previous = db.execute("SELECT * FROM measurements WHERE measurement_id=?", (case["latest_id"],)).fetchone()
            newer = (previous is None or previous["boot_id"] != payload.boot_id or payload.sequence > previous["sequence"])
            active = device_now["active_boot"] == payload.boot_id
            update = active and not payload.historical and newer
            if update:
                db.execute("UPDATE cases SET latest_id=? WHERE case_id=?", (measurement_id, device["case_id"]))
                self.prediction(db, measurement_id, case["revision"])
        return {"measurement_id": measurement_id, "received_at": received_at, "duplicate": False}, update

    def prediction(self, db, measurement_id, revision):
        saved = db.execute("SELECT data FROM predictions WHERE measurement_id=? AND revision=?", (measurement_id, revision)).fetchone()
        if saved:
            return json.loads(saved["data"])
        row = db.execute("SELECT * FROM measurements WHERE measurement_id=?", (measurement_id,)).fetchone()
        if row is None:
            raise DomainError(404, "not_found", "Medição não encontrada.")
        ctx = db.execute("SELECT data FROM contexts WHERE case_id=? AND revision=?", (row["case_id"], revision)).fetchone()
        result = {"measurement_id": measurement_id, "context_revision": revision if ctx else None,
                  "computed_at": now(), "status": "ready", "probabilidade": None,
                  "classificacao_risco": None, "reason": None, "window_samples": 0, "model_input": None}
        cutoff = (datetime.fromisoformat(row["received_at"].replace("Z", "+00:00")) - timedelta(seconds=15)).isoformat().replace("+00:00", "Z")
        readings = db.execute("SELECT data FROM measurements WHERE device_id=? AND boot_id=? AND sequence<=? AND received_at>=? ORDER BY sequence DESC LIMIT 20",
                              (row["device_id"], row["boot_id"], row["sequence"], cutoff)).fetchall()
        window = [json.loads(r["data"]) for r in readings if not json.loads(r["data"])["historical"]][:5]
        result["window_samples"] = len(window)
        current = json.loads(row["data"])
        if not ctx:
            result.update(status="missing_context", reason="Contexto sintético não configurado.")
        elif not window or not 10 <= current["temperatura"] <= 40 or any(not 50 <= r["bpm"] <= 150 for r in window):
            result.update(status="out_of_domain", reason="Leitura fora do domínio do modelo preditivo.")
        else:
            values = json.loads(ctx["data"]) | {"temperatura": current["temperatura"], "fc_media": sum(r["bpm"] for r in window) / len(window)}
            try:
                result.update(self.engine.predict(values), model_input=values)
            except (ValueError, OSError):
                result.update(status="model_unavailable", reason="Modelo preditivo indisponível.")
        db.execute("INSERT INTO predictions VALUES (?,?,?)", (measurement_id, revision, pack(result)))
        return result

    def dashboard(self, case_id, owner):
        with self.db.connect() as db:
            case = self.case(db, case_id, owner)
            row = db.execute("SELECT * FROM measurements WHERE measurement_id=?", (case["latest_id"],)).fetchone()
            prediction = self.prediction(db, row["measurement_id"], case["revision"]) if row else None
            analysis = db.execute("SELECT * FROM jobs WHERE case_id=? AND kind='analysis' AND status!='failed' ORDER BY rowid DESC LIMIT 1", (case_id,)).fetchone()
            measurement = {"measurement_id": row["measurement_id"], "received_at": row["received_at"], **json.loads(row["data"])} if row else None
        public_prediction = {k: v for k, v in prediction.items() if k != "model_input"} if prediction else None
        return {"case_id": case_id, "measurement": measurement, "context": self.context(case_id, owner),
                "prediction": public_prediction, "analysis": job_output(analysis) if analysis else None}

    def analysis_input(self, case_id, owner, measurement_id, revision):
        with self.db.connect() as db:
            self.case(db, case_id, owner)
            measurement = db.execute("SELECT case_id FROM measurements WHERE measurement_id=?", (measurement_id,)).fetchone()
            if measurement is None or measurement["case_id"] != case_id:
                raise DomainError(404, "not_found", "Medição não encontrada.")
            prediction = self.prediction(db, measurement_id, revision)
            if prediction["status"] != "ready":
                raise DomainError(422, prediction["status"], prediction["reason"])
            return prediction["model_input"]


def job_output(row):
    value = {"analysis_id" if row["kind"] == "analysis" else "message_id": row["job_id"],
             "measurement_id": row["measurement_id"], "context_revision": row["revision"],
             "status": row["status"], "requested_at": row["requested_at"], "completed_at": row["completed_at"],
             "error": json.loads(row["error"]) if row["error"] else None}
    if row["kind"] == "analysis":
        value["recommendation"] = None
    if row["result"] and row["status"] == "completed":
        value.update(json.loads(row["result"]))
    return value
