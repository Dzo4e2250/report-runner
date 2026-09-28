#!/usr/bin/env python3
"""Ustvari demo SQLite bazo z vzorcnimi nabavnimi narocili.

Nekaj narocil ima potrjeni rok KASNEJSI od zahtevanega — to so zadetki porocila.
"""
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "demo.db"
DB.parent.mkdir(exist_ok=True)
if DB.exists():
    DB.unlink()

conn = sqlite3.connect(DB)
conn.execute("""
CREATE TABLE narocila (
    id INTEGER PRIMARY KEY,
    stevilka_narocila TEXT NOT NULL,
    dobavitelj TEXT NOT NULL,
    datum_narocila TEXT NOT NULL,
    zahtevani_rok TEXT NOT NULL,
    potrjeni_rok TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'odprto',
    znesek_eur REAL NOT NULL
)
""")

vrstice = [
    ("NAB-2026-0101", "Helly Hansen Workwear", "2026-09-01", "2026-09-20", "2026-09-19", "odprto", 4200.00),
    ("NAB-2026-0102", "3M Slovenija",          "2026-09-02", "2026-09-22", "2026-09-29", "odprto", 1850.50),  # +7 dni
    ("NAB-2026-0103", "Uvex Safety",           "2026-09-03", "2026-09-25", "2026-09-25", "odprto", 960.00),
    ("NAB-2026-0104", "Delta Plus",            "2026-09-05", "2026-09-26", "2026-10-08", "odprto", 12700.00), # +12 dni
    ("NAB-2026-0105", "Honeywell",             "2026-09-08", "2026-09-30", "2026-10-02", "odprto", 3300.75),  # +2 dni
    ("NAB-2026-0106", "MSA Safety",            "2026-09-10", "2026-10-01", "2026-10-01", "potrjeno", 780.20),
    ("NAB-2026-0107", "3M Slovenija",          "2026-09-12", "2026-10-03", "2026-10-10", "odprto", 540.00),  # +7 dni
    ("NAB-2026-0108", "Atlas Schuhe",          "2026-09-15", "2026-10-05", "2026-10-12", "preklicano", 2100.00),  # preklicano - ne sme biti v porocilu
    ("NAB-2026-0109", "Pfanner",               "2026-09-18", "2026-10-08", "2026-10-06", "odprto", 1660.00),
    ("NAB-2026-0110", "Ejendals",              "2026-09-20", "2026-10-10", "2026-10-24", "odprto", 890.00),  # +14 dni
]
conn.executemany(
    "INSERT INTO narocila (stevilka_narocila, dobavitelj, datum_narocila, zahtevani_rok, potrjeni_rok, status, znesek_eur) VALUES (?,?,?,?,?,?,?)",
    vrstice,
)
conn.commit()
conn.close()
print(f"Demo baza ustvarjena: {DB} ({len(vrstice)} naročil, 5 zamujenih)")
