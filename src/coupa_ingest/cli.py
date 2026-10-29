"""Línea de comandos.

  coupa-ingest run [--dry-run] [--file X.xlsx] [--sheet NOMBRE ...]
  coupa-ingest secrets set graph_client_secret|coupa_api_key
  coupa-ingest check            (valida configuración y que existan los secretos)

Código de salida: 0 = correcto, 1 = falla de la corrida, 2 = error de configuración.
"""

from __future__ import annotations

import argparse
import logging
import uuid
from datetime import datetime
from pathlib import Path

from coupa_ingest import secrets
from coupa_ingest.config import load_settings
from coupa_ingest.logging_setup import setup_logging

DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "config" / "settings.toml"


def new_run_id() -> str:
    return f"{datetime.now():%Y%m%dT%H%M%S}_{uuid.uuid4().hex[:6]}"  # noqa: DTZ005 hora local del servidor


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="coupa-ingest")
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="Ejecuta una corrida")
    r.add_argument("--dry-run", action="store_true", help="Lee y genera CSV sin enviar")
    r.add_argument("--file", type=Path, help="Usar un .xlsx local en lugar de SharePoint")
    r.add_argument("--sheet", action="append", help="Limitar a esta pestaña (repetible)")
    r.add_argument("--run-id", help="Por defecto se genera uno")

    s = sub.add_parser("secrets", help="Administra secretos en el Administrador de credenciales")
    s.add_argument("action", choices=["set"])
    s.add_argument("name", choices=list(secrets.KNOWN))

    sub.add_parser("check", help="Valida configuración y secretos")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        settings = load_settings(args.config)
    except Exception as exc:  # noqa: BLE001
        print(f"Error de configuración ({args.config}): {exc}")
        return 2

    if args.cmd == "secrets":
        secrets.set_secret_interactive(args.name, settings.ambiente)
        print(f"Secreto {args.name} guardado para {settings.ambiente}.")
        return 0

    if args.cmd == "check":
        ok = True
        for name in secrets.KNOWN:
            try:
                secrets.get_secret(name, settings.ambiente)
                print(f"OK   secreto {name}")
            except secrets.MissingSecretError as exc:
                print(f"FALTA {exc}")
                ok = False
        print(f"Pestañas configuradas: {[s.sheet for s in settings.sheets]}")
        return 0 if ok else 2

    # run
    from coupa_ingest.pipeline import run  # import tardío: acelera `secrets` y `check`

    run_id = args.run_id or new_run_id()
    log_file = setup_logging(settings.log_dir, run_id)
    log = logging.getLogger("coupa_ingest")
    log.info("Inicio corrida (ambiente=%s, dry_run=%s)", settings.ambiente, args.dry_run)
    manifest = run(settings, run_id, args.dry_run, args.file, args.sheet)
    log.info("Fin corrida: %s. Log: %s", manifest.status, log_file)
    return 0 if manifest.status == "ok" else 1
