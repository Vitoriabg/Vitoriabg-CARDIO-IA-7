"""Interface de terminal: treinar, conferir localmente ou executar os agentes."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import RateLimitError
from pydantic import ValidationError

from .config import project_root
from .inference import RiskPredictor
from .planning import make_recommendation
from .protocols import select_protocols
from .schemas import PatientCase


def main() -> None:
    load_dotenv(project_root() / ".env", override=False)
    parser = argparse.ArgumentParser(description="CardioIA - Fase 6 (somente simulação acadêmica)")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("treinar", help="Gerar 5.000 casos, treinar, avaliar e salvar o modelo")
    for name in ["prever", "agentes"]:
        sub = commands.add_parser(name, help="Conferência local" if name == "prever" else "Executar o pipeline OpenAI Agents SDK")
        sub.add_argument("--caso", type=Path, default=project_root() / "data" / "exemplos" / "novo_caso.json")
        sub.add_argument("--saida", type=Path, help="Salvar a entrada e o resultado em JSON")
    try:
        args = parser.parse_args()
        if args.command == "treinar":
            from .training import train_and_save
            print(json.dumps(train_and_save(), ensure_ascii=False, indent=2))
            return
        case = PatientCase.model_validate(json.loads(args.caso.read_text(encoding="utf-8")))
        if args.command == "prever":
            prediction = RiskPredictor().predict(case)
            output = make_recommendation(prediction, select_protocols(case, prediction))
            result = {"modo": "conferencia_local_sem_agentes", "resultado": output.model_dump()}
        else:
            from .orchestrator import run_pipeline
            execution = asyncio.run(asyncio.wait_for(run_pipeline(case), timeout=240))
            result = {
                "modo": "openai_agents_sdk_llm_local", "llm": execution.llm,
                "resultado": execution.recommendation.model_dump(),
                "fluxo": execution.events, "historico": execution.history,
            }
        result["entrada"] = case.model_dump()
        serialized = json.dumps(result, ensure_ascii=False, indent=2)
        if args.saida:
            args.saida.parent.mkdir(parents=True, exist_ok=True)
            args.saida.write_text(serialized + "\n", encoding="utf-8")
        print(serialized)
    except RateLimitError as exc:
        print("Erro: o servidor Ollama local limitou a requisição. Aguarde e confira o serviço local.", file=sys.stderr)
        raise SystemExit(1) from exc
    except (ValueError, ValidationError, FileNotFoundError, OSError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    except Exception as exc:
        # Inclui erros de API, guardrail e limite de turnos sem publicar credenciais.
        print(f"Falha na execução ({type(exc).__name__}). Verifique a configuração e as validações do pipeline.", file=sys.stderr)
        raise SystemExit(1) from exc
