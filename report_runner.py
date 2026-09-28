#!/usr/bin/env python3
"""report-runner — obcasna porocila iz podatkovnih baz po e-posti.

Konfiguracija v config.yaml: povezave do baz, SQL poizvedbe, ura posiljanja,
prejemniki. Brez AI-ja — dnevno porocilo mora biti deterministicno in zanesljivo.
"""
from __future__ import annotations

import argparse
import csv
import html
import io
import os
import re
import smtplib
import sys
import time
from datetime import datetime
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
OUTBOX = ROOT / "outbox"


def expand_env(value):
    """Zamenja ${SPREMENLJIVKA} z vrednostjo iz okolja."""
    if isinstance(value, str):
        return re.sub(r"\$\{(\w+)\}", lambda m: os.environ.get(m.group(1), m.group(0)), value)
    if isinstance(value, list):
        return [expand_env(v) for v in value]
    if isinstance(value, dict):
        return {k: expand_env(v) for k, v in value.items()}
    return value


def load_config(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return expand_env(cfg)


def scheduled_times(report: dict) -> list[str]:
    sched = report.get("schedule", "07:00")
    return [sched] if isinstance(sched, str) else list(sched)


def execute_query(db_url: str, query: str):
    """Za SQLite zadostuje vgrajen sqlite3 (brez dodatnih odvisnosti);
    SQLAlchemy se uvozi sele, ko jo prava baza res rabi."""
    if db_url.startswith("sqlite:///"):
        import sqlite3

        conn = sqlite3.connect(db_url[len("sqlite:///"):])
        try:
            cur = conn.execute(query)
            columns = [d[0] for d in cur.description]
            rows = cur.fetchall()
        finally:
            conn.close()
        return columns, rows
    from sqlalchemy import create_engine, text

    engine = create_engine(db_url)
    with engine.connect() as conn:
        result = conn.execute(text(query))
        columns = list(result.keys())
        rows = [tuple(r) for r in result.fetchall()]
    return columns, rows


def render_html(report: dict, columns: list, rows: list) -> str:
    datum = datetime.now().strftime("%d. %m. %Y %H:%M")
    parts = [
        '<html><body style="font-family:Arial,sans-serif;font-size:14px;color:#222">',
        f"<h2 style=\"margin-bottom:4px\">{html.escape(report['email']['subject'].split('—')[0].strip())}</h2>",
        f"<p style='color:#666;margin-top:0'>Ustvarjeno: {datum} · Zadetkov: {len(rows)}</p>",
    ]
    if report.get("intro"):
        parts.append(f"<p>{html.escape(report['intro'])}</p>")
    if not rows:
        parts.append("<p><strong>Ni zadetkov.</strong> Vse je v redu.</p>")
    else:
        parts.append('<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;border-color:#ccc">')
        parts.append("<tr>" + "".join(
            f'<th style="background:#f0f0f0;text-align:left">{html.escape(str(c))}</th>' for c in columns
        ) + "</tr>")
        for row in rows:
            parts.append("<tr>" + "".join(
                f"<td>{html.escape('' if v is None else str(v))}</td>" for v in row
            ) + "</tr>")
        parts.append("</table>")
    parts.append("<p style='color:#999;font-size:12px'>Poslal report-runner</p></body></html>")
    return "\n".join(parts)


def render_csv(columns: list, rows: list) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(columns)
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8-sig")  # BOM, da Excel pravilno prebere šumnike


def send_email(report: dict, html_body: str, csv_bytes: bytes | None, csv_name: str) -> None:
    msg = MIMEMultipart()
    msg["From"] = os.environ["SMTP_FROM"]
    msg["To"] = ", ".join(report["email"]["to"])
    msg["Subject"] = report["email"]["subject"].format(
        datum=datetime.now().strftime("%d. %m. %Y"),
    )
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    if csv_bytes is not None:
        part = MIMEBase("text", "csv")
        part.set_payload(csv_bytes)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{csv_name}"')
        msg.attach(part)

    host = os.environ.get("SMTP_HOST", "localhost")
    port = int(os.environ.get("SMTP_PORT", "25"))
    with smtplib.SMTP(host, port, timeout=30) as smtp:
        if os.environ.get("SMTP_TLS", "false").lower() == "true":
            smtp.starttls()
        if os.environ.get("SMTP_USER"):
            smtp.login(os.environ["SMTP_USER"], os.environ.get("SMTP_PASSWORD", ""))
        smtp.send_message(msg)


def save_to_outbox(name: str, html_body: str, csv_bytes: bytes | None, csv_name: str) -> None:
    OUTBOX.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    (OUTBOX / f"{ts}-{name}.html").write_text(html_body, encoding="utf-8")
    if csv_bytes is not None:
        (OUTBOX / f"{ts}-{csv_name}").write_bytes(csv_bytes)
    print(f"  -> shranjeno v {OUTBOX}/ (SMTP ni nastavljen ali je --dry-run)")


def run_report(cfg: dict, report: dict, dry_run: bool = False) -> None:
    name = report["name"]
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Zazenjam porocilo: {name}")
    db_url = cfg["databases"][report["database"]]["url"]
    columns, rows = execute_query(db_url, report["query"])
    print(f"  Poizvedba: {len(rows)} zadetkov")
    html_body = render_html(report, columns, rows)
    csv_bytes = csv_name = None
    if report.get("attach_csv", True):
        csv_name = f"{name}.csv"
        csv_bytes = render_csv(columns, rows)
    if dry_run or not os.environ.get("SMTP_HOST"):
        save_to_outbox(name, html_body, csv_bytes, csv_name)
    else:
        send_email(report, html_body, csv_bytes, csv_name)
        print(f"  Poslano na: {', '.join(report['email']['to'])}")


def cmd_run(cfg: dict, args) -> None:
    reports = cfg["reports"]
    if args.all:
        todo = reports
    elif args.report:
        todo = [r for r in reports if r["name"] == args.report]
        if not todo:
            sys.exit(f"Napaka: porocila '{args.report}' ni v konfiguraciji.")
    else:  # --due: samo porocila, ki so na vrsti v tej minuti (za cron vsako minuto)
        now = datetime.now().strftime("%H:%M")
        todo = [r for r in reports if now in scheduled_times(r)]
        if not todo:
            print(f"[{datetime.now():%H:%M}] Ni porocil na vrsti.")
            return
    for report in todo:
        run_report(cfg, report, dry_run=args.dry_run)


def cmd_serve(cfg: dict, args) -> None:
    """Notranji razporejevalec (za Docker). Sprozi porocilo ob uri, tudi ce je bil
    streznik takrat ugasnjen (enkrat na dan, ob prvi priliki)."""
    fired: dict[str, str] = {}  # "ime|HH:MM" -> datum zadnjega sprozenja
    print("Razporejevalec tece. Razpored:")
    for r in cfg["reports"]:
        print(f"  {r['name']}: vsak dan ob {', '.join(scheduled_times(r))}")
    while True:
        now = datetime.now()
        for r in cfg["reports"]:
            for t in scheduled_times(r):
                hh, mm = map(int, t.split(":"))
                key = f"{r['name']}|{t}"
                due = (now.hour, now.minute) >= (hh, mm)
                if due and fired.get(key) != now.strftime("%Y-%m-%d"):
                    fired[key] = now.strftime("%Y-%m-%d")
                    try:
                        run_report(cfg, r, dry_run=args.dry_run)
                    except Exception as e:  # eno slabo porocilo ne sme ustaviti ostalih
                        print(f"  NAPAKA pri {r['name']}: {e}", file=sys.stderr)
        time.sleep(30)


def cmd_test_email(cfg: dict, args) -> None:
    report = {
        "name": "test",
        "email": {"to": args.to, "subject": "report-runner — testno sporocilo"},
        "intro": "Ce to berete, e-posta deluje.",
        "attach_csv": False,
    }
    body = render_html(report, [], [])
    if not os.environ.get("SMTP_HOST"):
        save_to_outbox("test", body, None, "")
    else:
        send_email(report, body, None, "")
        print(f"Testno sporocilo poslano na: {', '.join(args.to)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Obcasna porocila iz baz po e-posti.")
    parser.add_argument("--config", default=str(ROOT / "config.yaml"))
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="sprozi porocila (privzeto: tista na vrsti zdaj)")
    p_run.add_argument("--report", help="ime porocila iz config.yaml (takoj, ne glede na uro)")
    p_run.add_argument("--all", action="store_true", help="vsa porocila takoj")
    p_run.add_argument("--dry-run", action="store_true", help="ne posiljaj, shrani v outbox/")

    p_serve = sub.add_parser("serve", help="notranji razporejevalec (za Docker)")
    p_serve.add_argument("--dry-run", action="store_true")

    p_test = sub.add_parser("test-email", help="poslji testno sporocilo")
    p_test.add_argument("--to", nargs="+", required=True)

    args = parser.parse_args()
    if Path(ROOT / ".env").exists():
        for line in (ROOT / ".env").read_text().splitlines():
            if line.strip() and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())
    cfg = load_config(args.config)
    {"run": cmd_run, "serve": cmd_serve, "test-email": cmd_test_email}[args.command](cfg, args)


if __name__ == "__main__":
    main()
