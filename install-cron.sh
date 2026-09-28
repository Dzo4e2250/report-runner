#!/usr/bin/env bash
# Doda cron vnos: vsako minuto preveri, ali je kaksno porocilo na vrsti.
# Razpored sam se nastavlja v config.yaml (polje schedule) — cron tu samo "budi" program.
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${DIR}/venv/bin/python"
[ -x "$PYTHON" ] || PYTHON="$(command -v python3)"

VRSTICA="* * * * * cd ${DIR} && ${PYTHON} report_runner.py run >> ${DIR}/report-runner.log 2>&1"

( crontab -l 2>/dev/null | grep -v "report_runner.py run" ; echo "$VRSTICA" ) | crontab -
echo "Cron vnos dodan:"
echo "  $VRSTICA"
echo "Odstranis ga s: crontab -e  (izbrisi vrstico)"
