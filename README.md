# report-runner

Občasna poročila iz podatkovnih baz po e-pošti — nastavljiva z eno YAML datoteko.

**Kaj naredi:** poveže se na bazo (PostgreSQL, MySQL/MariaDB, SQLite, SQL Server),
izvede nastavljeno SQL poizvedbo ("vprašanje"), rezultat oblikuje v pregleden HTML e-mail
s CSV prilogo in ga ob izbrani uri pošlje prejemnikom. Deluje na Linux strežniku (cron)
ali v Dockerju (notranji razporejevalec).

Primer, ki je priložen: *seznam naročil, pri katerih je dobavitelj potrdil kasnejši rok
od zahtevanega, vsak dan ob 7:00.*

---

## Hiter zagon (demo v 2 minutah, brez pošiljanja e-pošte)

```bash
git clone <repo> && cd report-runner
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

python demo/make_demo_db.py          # ustvari testno SQLite bazo
cp config.example.yaml config.yaml
python report_runner.py run --all --dry-run
```

Rezultat (HTML e-mail + CSV) se namesto pošiljanja shrani v `outbox/` — odprite v brskalniku.

## Docker

```bash
cp config.example.yaml config.yaml   # uredite poizvedbe, ure, prejemnike
cp .env.example .env                 # vnesite SMTP podatke (sicer gre v outbox/)
docker compose up -d --build
```

Kontejner teče stalno in sproži poročila ob nastavljenih urah (tudi če je bil ob uri
ugasnjen — poročilo se pošlje ob prvi priliki tisti dan).

## Namestitev na Linux strežnik (cron)

```bash
sudo apt install python3-venv    # samo na Debian/Ubuntu, enkrat
git clone <repo> && cd report-runner
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp config.example.yaml config.yaml && cp .env.example .env   # dopolni obe
./install-cron.sh
```

`install-cron.sh` doda en sam cron vnos, ki vsako minuto preveri, ali je kakšno poročilo
na vrsti. **Ure se nastavljajo v `config.yaml`, ne v crontabu** — sprememba razporeda
tako ne zahteva ukvarjanja s cronjem.

## Konfiguracija (`config.yaml`)

```yaml
databases:
  erp:
    url: ${ERP_DB_URL}     # povezava; gesla drži v .env, ne tukaj

reports:
  - name: zamujena-narocila
    database: erp
    schedule: "07:00"                    # ali več ur: ["07:00", "15:30"]
    intro: "Besedilo na vrhu e-pošte."
    query: |
      SELECT ...                         # vaše "vprašanje" — poljuben SQL
    email:
      to: [odgovorna.oseba@podjetje.si, sef@podjetje.si]
      subject: "Zamujena naročila — {datum}"
    attach_csv: true                     # priloga CSV (Excel, s šumniki)
```

Novo poročilo = nov blok v `config.yaml`. Brez sprememb kode, brez ponovne namestitve.

## Uporabni ukazi

| Ukaz | Kaj |
|---|---|
| `python report_runner.py run` | sproži poročila, ki so na vrsti v tej minuti (za cron) |
| `python report_runner.py run --report IME` | eno poročilo takoj, ne glede na uro |
| `python report_runner.py run --all --dry-run` | vsa poročila, brez pošiljanja (test) |
| `python report_runner.py serve` | notranji razporejevalec (za Docker) |
| `python report_runner.py test-email --to nekdo@podjetje.si` | preveri SMTP nastavitve |

## Povezava na pravo bazo

V `config.yaml` dodajte bazo in v `.env` njeno povezavo:

```env
ERP_DB_URL=postgresql://user:geslo@streznik:5432/baza
```

| Baza | URL primer | Gonilnik |
|---|---|---|
| PostgreSQL | `postgresql://user:geslo@host:5432/db` | psycopg2 (v requirements) |
| MySQL/MariaDB | `mysql+pymysql://user:geslo@host:3306/db` | pymysql (v requirements) |
| SQLite | `sqlite:///data/baza.db` | vgrajen |
| SQL Server | `mssql+pyodbc://user:geslo@host/db?driver=ODBC+Driver+18+for+SQL+Server` | pyodbc + sistemski ODBC gonilnik |

## Varnost

- Gesla in povezave so **samo v `.env`** — datoteka je v `.gitignore` in ne gre na GitHub.
- Program izvaja samo `SELECT` poizvedbe, ki jih napišete sami; za dostop do baze
  priporočamo uporabnika samo z bralnimi pravicami.
- E-pošta gre prek TLS (nastavljivo).

## Katera orodja sem uporabil in zakaj

| Orodje | Zakaj |
|---|---|
| **Python 3** | stabilen, povsod prisoten, odlične knjižnice za baze in e-pošto |
| **SQLAlchemy** | ena ista koda deluje nad vsemi bazami — zamenjava baze pomeni samo drug URL |
| **YAML za konfiguracijo** | bere ga tudi netehnična oseba; novo poročilo dodaš brez programiranja |
| **SMTP** | standard — deluje z vsakim poštnim strežnikom (M365, Google, lastni) |
| **cron / Docker** | dve standardni poti namestitve; cron je tam, kjer že tečejo strežniki, Docker tam, kjer hočeš izolacijo |
| **zavestno BREZ AI-ja** | dnevno poročilo ob 7:00 mora biti deterministično: enak vhod → enak izhod, brez stroška po API klicih in brez točke odpovedi, ko LLM ni dosegljiv. AI ima smisel pri *pisanju* poizvedb, ne pri njihovem *izvajanju*. |

## Struktura

```
report_runner.py       # cel program (~250 vrstic, brez odvisnosti poleg 2 knjižnic)
config.example.yaml    # primer konfiguracije (kopiraš v config.yaml)
demo/make_demo_db.py   # ustvari testno SQLite bazo z vzorčnimi naročili
install-cron.sh        # doda cron vnos na Linuxu
Dockerfile, docker-compose.yml
.env.example           # predloga za SMTP in povezave do baz
```
