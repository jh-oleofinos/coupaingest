"""Línea de comandos.

  coupa-ingest run [--dry-run] [--file X.xlsx] [--sheet NOMBRE ...]
  coupa-ingest secrets set graph_client_secret|coupa_api_key
  coupa-ingest check [--conexion]   (configuración, secretos y, opcional, acceso real a Datasphere)
  coupa-ingest login                (inicia sesión en Microsoft 365 una vez; sharepoint.auth = "usuario")
  coupa-ingest modelos              (lista los modelos que ve la API key; sirve para el model_id)

Código de salida: 0 = correcto, 1 = falla de la corrida, 2 = configuración o secretos.
"""

from __future__ import annotations

import argparse
import logging
import uuid
from datetime import datetime
from pathlib import Path

from coupa_ingest import secrets
from coupa_ingest.config import default_config_path, load_settings
from coupa_ingest.logging_setup import setup_logging


def new_run_id() -> str:
    return f"{datetime.now():%Y%m%dT%H%M%S}_{uuid.uuid4().hex[:6]}"  # noqa: DTZ005 hora local del servidor


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="coupa-ingest")
    p.add_argument("--config", type=Path, default=None,
                   help="Por defecto: $COUPA_INGEST_CONFIG o <repo>/config/settings.toml")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="Ejecuta una corrida (descarga de SharePoint y envía)")
    r.add_argument("--dry-run", action="store_true", help="Descarga y genera CSV sin enviar")
    r.add_argument("--file", type=Path, help="Solo pruebas: usar un .xlsx local en lugar de SharePoint")
    r.add_argument("--sheet", action="append", help="Limitar a esta pestaña (repetible)")
    r.add_argument("--run-id", help="Por defecto se genera uno")

    s = sub.add_parser("secrets", help="Administra secretos en el Administrador de credenciales")
    s.add_argument("action", choices=["set"])
    s.add_argument("name", choices=list(secrets.KNOWN))

    c = sub.add_parser("check", help="Valida configuración y secretos")
    c.add_argument("--conexion", action="store_true",
                   help="Además prueba el acceso real al archivo en SharePoint (sin descargarlo)")

    sub.add_parser("login", help="Inicia sesión en Microsoft 365 para leer el archivo (una vez)")
    sub.add_parser("modelos", help="Lista los modelos de llama.ai visibles con la API key")
    return p


def _check(settings, conexion: bool) -> int:
    ok = True
    pend = settings.placeholders()
    if pend:
        print(f"PENDIENTE valores de ejemplo en settings.toml: {', '.join(pend)}")
        ok = False
    needed = [secrets.COUPA_API_KEY]
    if settings.source == "datasphere":
        needed.append(secrets.DATASPHERE_PASSWORD)
    elif settings.sharepoint and settings.sharepoint.auth == "app":
        needed.append(secrets.GRAPH_CLIENT_SECRET)
    for name in needed:
        try:
            secrets.get_secret(name, settings.ambiente)
            print(f"OK    secreto {name}")
        except secrets.MissingSecretError as exc:
            print(f"FALTA {exc}")
            ok = False
    if settings.source == "datasphere" and settings.datasphere:
        ds = settings.datasphere
        print(f"Origen: Datasphere {ds.host}:{ds.port} · usuario {ds.user} · esquema {ds.schema_}"
              f" · {len(ds.views)} vistas")
    else:
        print(f"Origen: Excel · pestañas: "
              f"{'todas' if settings.all_sheets else [s.sheet for s in settings.sheets]}"
              f" · excluidas: {settings.exclude_sheets or 'ninguna'}"
              f" · ocultas: {'sí' if settings.include_hidden_sheets else 'no'}")
    ds_pend = [p for p in pend if p.startswith("datasphere")]
    if conexion and settings.source == "datasphere" and not ds_pend:
        from coupa_ingest.datasphere import DatasphereClient

        try:
            password = secrets.get_secret(secrets.DATASPHERE_PASSWORD, settings.ambiente)
            with DatasphereClient(settings.datasphere, password) as dsc:
                counts = dsc.check(settings.datasphere.views)
            print("OK    Datasphere: conexión y vistas visibles")
            for view, n in counts.items():
                print(f"        {view}: {n:,} filas")
            print(f"        total: {sum(counts.values()):,} filas")
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR Datasphere: {exc}")
            ok = False
    elif conexion and settings.source == "sharepoint":
        from coupa_ingest.sharepoint import client_from_settings

        try:
            meta = client_from_settings(settings).get_metadata()
            print(f"OK    SharePoint: {meta['name']} ({meta['size']} bytes, "
                  f"modificado {meta['lastModifiedDateTime']} por {meta['lastModifiedBy']})")
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR SharePoint: {exc}")
            ok = False
    return 0 if ok else 2


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config_path = args.config or default_config_path()
    try:
        settings = load_settings(config_path)
    except Exception as exc:  # noqa: BLE001
        print(f"Error de configuración ({config_path}): {exc}")
        return 2

    if args.cmd == "secrets":
        secrets.set_secret_interactive(args.name, settings.ambiente)
        print(f"Secreto {args.name} guardado para {settings.ambiente}.")
        return 0

    if args.cmd == "check":
        return _check(settings, args.conexion)

    if args.cmd == "login":
        from coupa_ingest.sharepoint import client_from_settings

        if not settings.sharepoint or settings.sharepoint.auth != "usuario":
            print("login solo aplica con sharepoint.auth = \"usuario\"")
            return 2
        sp = client_from_settings(settings)
        print(f"Sesión guardada para {sp.login()}. Probando acceso al archivo...")
        meta = sp.get_metadata()
        print(f"OK    {meta['name']} ({meta['size']} bytes, modificado {meta['lastModifiedDateTime']} "
              f"por {meta['lastModifiedBy']})")
        return 0

    if args.cmd == "modelos":
        import json

        from coupa_ingest.coupa_client import CoupaClient

        client = CoupaClient(settings.coupa, secrets.get_secret(secrets.COUPA_API_KEY, settings.ambiente))
        print(json.dumps(client.list_models(), ensure_ascii=False, indent=2))
        return 0

    # run
    from coupa_ingest.pipeline import run  # import tardío: acelera `secrets` y `check`

    run_id = args.run_id or new_run_id()
    log_file = setup_logging(settings.log_dir, run_id)
    log = logging.getLogger("coupa_ingest")
    pend = settings.placeholders()
    if args.file:      # con archivo local no se usa ni SharePoint ni Datasphere
        pend = [p for p in pend if not p.startswith(("sharepoint", "datasphere"))]
    if args.dry_run:   # sin envío no se usa Coupa
        pend = [p for p in pend if not p.startswith("coupa.")]
    if pend:
        log.error("Configuración incompleta (valores de ejemplo): %s", ", ".join(pend))
        return 2
    log.info("Inicio corrida (ambiente=%s, dry_run=%s)", settings.ambiente, args.dry_run)
    manifest = run(settings, run_id, args.dry_run, args.file, args.sheet)
    log.info("Fin corrida: %s%s. Log: %s", manifest.status,
             " (sin envío: archivo sin cambios)" if manifest.skipped else "", log_file)
    return 0 if manifest.status == "ok" else 1
