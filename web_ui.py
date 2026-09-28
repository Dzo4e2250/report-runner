#!/usr/bin/env python3
"""Lokalni spletni vmesnik za report-runner.

Zagon:  python3 web_ui.py
Naslov: http://localhost:8734  (vezan samo na 127.0.0.1 — ni vidna zunaj)
"""
import html
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import yaml

import report_runner as rr

PORT = 8734
CONFIG = rr.ROOT / "config.yaml"

CSS = """
body{font-family:Arial,sans-serif;max-width:960px;margin:24px auto;padding:0 16px;color:#222}
h1{font-size:22px} h2{font-size:17px;margin-top:32px}
label{display:block;font-size:12px;color:#555;margin-top:10px}
input[type=text],textarea,select{width:100%;box-sizing:border-box;padding:6px;font-size:14px;
  border:1px solid #bbb;border-radius:4px;font-family:inherit}
textarea.query{font-family:monospace;font-size:13px}
button{margin-top:12px;padding:8px 18px;font-size:14px;border:0;border-radius:4px;
  background:#0a5;color:#fff;cursor:pointer}
button.sec{background:#468} button.del{background:#b33;padding:4px 10px;margin-top:0}
details{border:1px solid #ddd;border-radius:6px;padding:10px 14px;margin-top:10px}
summary{cursor:pointer;font-weight:bold}
.flash{background:#e7f7e7;border:1px solid #9c9;padding:10px;border-radius:6px;margin:12px 0}
.note{color:#777;font-size:13px}
table.dbs td{padding:4px 8px 4px 0}
"""


def load_cfg() -> dict:
    src = CONFIG if CONFIG.exists() else rr.ROOT / "config.example.yaml"
    return yaml.safe_load(src.read_text(encoding="utf-8")) or {}


def esc(v) -> str:
    return html.escape("" if v is None else str(v))


def page(msg: str = "") -> bytes:
    cfg = load_cfg()
    smtp_ok = bool(__import__("os").environ.get("SMTP_HOST")) or (rr.ROOT / ".env").exists()
    out = [f"<html><head><meta charset=utf-8><title>report-runner</title><style>{CSS}</style></head><body>"]
    out.append("<h1>report-runner — nastavitve</h1>")
    out.append(f"<p class=note>Lokalni vmesnik · spremembe se shranjujejo v <code>config.yaml</code> · "
               f"e-pošta: {'SMTP nastavljen' if smtp_ok else '<b>ni nastavljen</b> — zagon shrani v outbox/'}</p>")
    if msg:
        out.append(f"<div class=flash>{esc(msg)}</div>")

    # --- baze ---
    out.append('<h2>Podatkovne baze</h2><form method=post action="/save-dbs"><table class=dbs>')
    for name, db in (cfg.get("databases") or {}).items():
        out.append(f'<tr><td><b>{esc(name)}</b></td>'
                   f'<td style="width:100%"><input type=text name="db__{esc(name)}" value="{esc(db.get("url",""))}"></td></tr>')
    out.append('<tr><td><input type=text name="new_db_name" placeholder="ime-nove-baze"></td>'
               '<td style="width:100%"><input type=text name="new_db_url" placeholder="npr. postgresql://... ali sqlite:///data/baza.db"></td></tr>')
    out.append('</table><button>Shrani baze</button></form>')

    # --- porocila ---
    out.append("<h2>Poročila</h2>")
    for i, r in enumerate(cfg.get("reports") or []):
        sched = r.get("schedule", "07:00")
        sched = ", ".join(sched) if isinstance(sched, list) else sched
        out.append(f"""
<details {'open' if len(cfg.get('reports') or [])==1 else ''}>
<summary>{esc(r.get('name',''))} — vsak dan ob {esc(sched)} → {esc(', '.join(r.get('email',{}).get('to',[])))}</summary>
<form method=post action="/save-report">
<input type=hidden name=idx value={i}>
<label>Ime poročila (brez presledkov)</label>
<input type=text name=name value="{esc(r.get('name',''))}">
<label>Baza</label>
<select name=database>{''.join(f'<option {"selected" if d==r.get("database") else ""}>{esc(d)}</option>' for d in (cfg.get("databases") or {}))}</select>
<label>Ura pošiljanja (ena ali več, ločenih z vejico)</label>
<input type=text name=schedule value="{esc(sched)}">
<label>Prejemniki (vsak v svojo vrstico)</label>
<textarea name=to rows=2>{esc(chr(10).join(r.get('email',{}).get('to',[])))}</textarea>
<label>Zadeva e-pošte (lahko vsebuje {{datum}})</label>
<input type=text name=subject value="{esc(r.get('email',{}).get('subject',''))}">
<label>Uvodno besedilo v mailu</label>
<input type=text name=intro value="{esc(r.get('intro',''))}">
<label>SQL poizvedba ("vprašanje")</label>
<textarea class=query name=query rows=8>{esc(r.get('query',''))}</textarea>
<label><input type=checkbox name=attach_csv style="width:auto" {'checked' if r.get('attach_csv',True) else ''}> priloži CSV</label>
<button>Shrani poročilo</button>
<button class=sec formmethod=post formaction="/run" formnovalidate>Zaženi zdaj (test, brez pošiljanja)</button>
<button class=del formmethod=post formaction="/delete-report" formnovalidate>Izbriši</button>
</form></details>""")

    out.append("""
<details><summary>+ Novo poročilo</summary>
<form method=post action="/save-report">
<input type=hidden name=idx value=-1>
<label>Ime poročila (brez presledkov)</label><input type=text name=name required>
<label>Baza</label><select name=database>""" +
    "".join(f"<option>{esc(d)}</option>" for d in (cfg.get("databases") or {})) + """</select>
<label>Ura pošiljanja</label><input type=text name=schedule value="07:00">
<label>Prejemniki (vsak v svojo vrstico)</label><textarea name=to rows=2></textarea>
<label>Zadeva</label><input type=text name=subject value="Poročilo — {datum}">
<label>Uvodno besedilo</label><input type=text name=intro>
<label>SQL poizvedba</label><textarea class=query name=query rows=6>SELECT ...</textarea>
<label><input type=checkbox name=attach_csv style="width:auto" checked> priloži CSV</label>
<button>Ustvari</button></form></details>

<h2>Zadnji rezultati (outbox)</h2><ul>""")
    outbox = sorted(rr.OUTBOX.glob("*.html"), reverse=True)[:10] if rr.OUTBOX.exists() else []
    out.extend(f'<li><a href="/outbox/{f.name}">{esc(f.name)}</a></li>' for f in outbox)
    out.append("</ul></body></html>")
    return "".join(out).encode("utf-8")


def save_cfg(cfg: dict) -> None:
    CONFIG.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")


class Handler(BaseHTTPRequestHandler):
    def _send(self, body: bytes, ctype="text/html; charset=utf-8", code=200):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, msg: str):
        self.send_response(303)
        self.send_header("Location", "/?msg=" + __import__("urllib.parse", fromlist=["quote"]).quote(msg))
        self.end_headers()

    def log_message(self, *a):
        pass

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/":
            msg = parse_qs(url.query).get("msg", [""])[0]
            self._send(page(msg))
        elif url.path.startswith("/outbox/"):
            f = rr.OUTBOX / Path(url.path).name
            if f.exists() and f.suffix in (".html", ".csv"):
                ctype = "text/html; charset=utf-8" if f.suffix == ".html" else "text/csv; charset=utf-8"
                self._send(f.read_bytes(), ctype)
            else:
                self._send(b"ni datoteke", code=404)
        else:
            self._send(b"404", code=404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        form = {k: v[0] for k, v in parse_qs(self.rfile.read(length).decode("utf-8")).items()}
        cfg = load_cfg()
        cfg.setdefault("databases", {})
        cfg.setdefault("reports", [])

        if self.path == "/save-dbs":
            for k, v in form.items():
                if k.startswith("db__") and v.strip():
                    cfg["databases"][k[4:]] = {"url": v.strip()}
            if form.get("new_db_name", "").strip() and form.get("new_db_url", "").strip():
                cfg["databases"][form["new_db_name"].strip()] = {"url": form["new_db_url"].strip()}
            save_cfg(cfg)
            self._redirect("Baze shranjene.")

        elif self.path == "/save-report":
            report = {
                "name": form["name"].strip(),
                "database": form["database"],
                "schedule": [t.strip() for t in form["schedule"].split(",") if t.strip()] or ["07:00"],
                "intro": form.get("intro", ""),
                "query": form["query"],
                "email": {
                    "to": [e.strip() for e in form["to"].splitlines() if e.strip()],
                    "subject": form["subject"],
                },
                "attach_csv": form.get("attach_csv") == "on",
            }
            if len(report["schedule"]) == 1:
                report["schedule"] = report["schedule"][0]
            idx = int(form["idx"])
            if idx == -1:
                cfg["reports"].append(report)
            else:
                cfg["reports"][idx] = report
            save_cfg(cfg)
            self._redirect(f"Poročilo '{report['name']}' shranjeno.")

        elif self.path == "/delete-report":
            idx = int(form["idx"])
            gone = cfg["reports"].pop(idx)
            save_cfg(cfg)
            self._redirect(f"Poročilo '{gone['name']}' izbrisano.")

        elif self.path == "/run":
            idx = int(form["idx"])
            report = cfg["reports"][idx]
            before = set(rr.OUTBOX.glob("*.html")) if rr.OUTBOX.exists() else set()
            try:
                rr.run_report(cfg, report, dry_run=True)
            except Exception as e:
                self._redirect(f"NAPAKA: {e}")
                return
            new = sorted(set(rr.OUTBOX.glob("*.html")) - before, key=lambda f: f.stat().st_mtime)
            if new:
                self.send_response(303)
                self.send_header("Location", f"/outbox/{new[-1].name}")
                self.end_headers()
            else:
                self._redirect("Zagnano, a ni nove datoteke.")
        else:
            self._send(b"404", code=404)


if __name__ == "__main__":
    print(f"Vmesnik tece na http://localhost:{PORT}  (ustavi s Ctrl+C)")
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
