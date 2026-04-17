# ETL by Claude — NBA Stats Pipeline

Ein vollständiger, produktionsnaher **ETL-Stack** von der lokalen Entwicklung bis zum Cloud-Deployment.
Gebaut mit modernen Data Engineering & DevOps-Prinzipien — Schritt für Schritt erklärt.

---

## Was ist das hier überhaupt?

Stell dir vor, du willst Daten automatisch von einer Quelle holen, aufbereiten und in eine Datenbank speichern — und das soll nicht nur einmal händisch klappen, sondern **zuverlässig, wiederholbar und automatisiert** funktionieren.

Genau das ist ein **ETL-Pipeline**:

```
Extract → Transform → Load
Holen  →  Aufbereiten  →  Speichern
```

In diesem Projekt holen wir **NBA-Spielerstatistiken** aus einer öffentlichen API,
berechnen einen eigenen Effizienz-Score und speichern alles in eine PostgreSQL-Datenbank.

---

## Die große Architektur (Ziel)

```
┌─────────────────────────────────────────────────────────────────┐
│  Lokale Entwicklung                                             │
│                                                                 │
│  ETL-Repository ──► Docker Container ──► Datenbank (DIH)        │
│  (dein Code)         (verpackt & isoliert)  (PostgreSQL)        │
└─────────────────────────────────────────────────────────────────┘
         │
         │ git push
         ▼
┌─────────────────────────────────────────────────────────────────┐
│  CI/CD Pipeline (GitHub Actions)                                │
│                                                                 │
│  Code ändern → Push → Pipeline läuft automatisch               │
│  → Container wird gebaut → in Registry gespeichert             │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│  GitOps & Cloud (Kubernetes + ArgoCD + Airflow)                 │
│                                                                 │
│  ArgoCD erkennt neue Version → Airflow plant Ausführung         │
│  → Container läuft in der Cloud → Daten landen in der DB        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Lokales Setup ✅

**Was haben wir hier?**

```
etl-project/
├── docker-compose.yml        ← startet die lokale Datenbank
├── .env                      ← Zugangsdaten (Passwörter, etc.) — wird NICHT nach GitHub gepusht
├── .env.example              ← Vorlage für Zugangsdaten (ohne echte Werte)
└── etl-repository/
    ├── Dockerfile            ← Bauplan für den Container
    ├── requirements.txt      ← Python-Pakete die wir brauchen
    └── src/
        └── etl.py            ← Das Herzstück: der ETL-Code
```

---

### Was ist Docker und warum benutzen wir es?

**Das Problem ohne Docker:**
> "Bei mir läuft's!" — aber auf dem Server, beim Kollegen oder in der Cloud sieht es anders aus.
> Jeder hat eine andere Python-Version, andere Pakete, andere Betriebssystem-Einstellungen.

**Die Lösung: Container**

Ein Container ist wie eine **Fertig-Umzugsbox**: Alles was dein Programm braucht
(Python, alle Pakete, der Code selbst) ist darin verpackt. Die Box läuft überall gleich —
egal ob auf deinem Laptop, einem Server in Frankfurt oder einer Cloud in den USA.

```
Dockerfile = Bauplan der Box
docker build = Box packen
docker run   = Box öffnen und Programm starten
```

### Was ist `docker-compose.yml`?

Wenn du mehrere Container brauchst (z.B. Datenbank + ETL-Code), startest du sie nicht
einzeln — `docker-compose` startet alle auf einmal mit einer einzigen Datei.

```yaml
# docker-compose.yml — vereinfacht erklärt:
services:
  postgres:        # ← starte einen Datenbankserver
    image: postgres:16  # ← benutze das offizielle PostgreSQL-Image
    ports:
      - "5432:5432"     # ← mach Port 5432 von außen erreichbar
```

**Starten mit:**
```bash
docker compose up -d
# -d = "detached" = läuft im Hintergrund, du siehst nicht den ganzen Output
```

---

### Was ist `.env` und warum ist das wichtig?

Passwörter und Zugangsdaten gehören **niemals direkt in den Code** oder nach GitHub.
Warum? Weil GitHub öffentlich ist (oder sein kann) — und einmal hochgeladene Passwörter
gelten als kompromittiert, auch wenn du sie später löschst.

Die Lösung: eine `.env`-Datei, die nur lokal existiert und in `.gitignore` steht.

```bash
# .env — deine geheimen Werte
POSTGRES_USER=etl_user
POSTGRES_PASSWORD=etl_password
POSTGRES_DB=nba_dih
```

```bash
# .gitignore — sagt Git: "Diese Datei ignorieren"
.env
```

Die `.env.example`-Datei zeigt die Struktur ohne echte Werte — die darf nach GitHub.

---

### Der ETL-Code erklärt (`src/etl.py`)

#### Extract — Daten holen

```python
def extract() -> pl.DataFrame:
    # Wir rufen die offizielle NBA API auf
    # Kein API-Key nötig, komplett kostenlos
    response = leagueleaders.LeagueLeaders(season="2024-25", ...)
    # Ergebnis: 231 Spieler mit ihren Statistiken
```

Wir benutzen das Python-Paket `nba_api` — eine fertige Schnittstelle zur offiziellen
NBA-Statistik-Datenbank. Kein Account, kein Key, einfach aufrufen.

#### Transform — Daten aufbereiten

```python
def transform(df: pl.DataFrame) -> pl.DataFrame:
    # Nur die relevanten Spalten behalten
    df = df.select(["player", "team", "pts", "ast", "reb", ...])

    # Eigenen Effizienz-Score berechnen
    # Punkte + Assists (x1.5) + Rebounds (x1.2) + Steals (x2) + Blocks (x2) - Turnover
    df = df.with_columns([
        (pl.col("pts") + pl.col("ast") * 1.5 + ...).alias("efficiency_score")
    ])
```

Wir benutzen **Polars** — eine moderne, sehr schnelle Python-Bibliothek für Datentransformation.
Vergleichbar mit Excel-Formeln, aber für Millionen von Zeilen und als Code.

#### Load — Daten speichern

```python
def load(df: pl.DataFrame) -> None:
    # Verbindung zur PostgreSQL-Datenbank aufbauen
    with psycopg.connect(...) as conn:
        # Tabelle anlegen falls nicht vorhanden
        conn.execute("CREATE TABLE IF NOT EXISTS nba_player_stats (...)")
        # Alte Daten löschen (wir wollen immer den aktuellen Stand)
        conn.execute("TRUNCATE TABLE nba_player_stats")
        # Neue Daten einfügen
        conn.executemany("INSERT INTO nba_player_stats ...", rows)
```

**PostgreSQL** ist unsere Datenbank — der "DIH" (Data Integration Hub) aus der Architektur.
Lokal läuft er als Docker Container, später in der Cloud auf Kubernetes.

---

### Das Dockerfile erklärt

```dockerfile
FROM python:3.12-slim
# ↑ Starte mit einem offiziellen Python-Image (schlank, nur das Nötigste)

WORKDIR /app
# ↑ Arbeitsverzeichnis im Container (wie "cd /app")

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# ↑ Pakete installieren — dieser Schritt wird gecacht, läuft nur neu wenn
#   requirements.txt sich ändert (macht Builds schneller)

COPY src/ ./src/
# ↑ Unseren Code in den Container kopieren

CMD ["python", "src/etl.py"]
# ↑ Was soll laufen wenn der Container startet?
```

**Warum erst requirements.txt, dann src/?**
Docker cached Layer-für-Layer. Wenn du nur deinen Code änderst aber nicht die Pakete,
muss Docker nicht alles neu installieren — nur die geänderten Layer werden neu gebaut.
Das spart enorm Zeit.

---

## Lokales Setup ausführen

### Voraussetzungen
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installiert
- Python 3.10+ installiert
- Git installiert

### Schritt 1: Repo klonen
```bash
git clone <repo-url>
cd etl-project
```

### Schritt 2: Zugangsdaten anlegen
```bash
cp .env.example .env
# .env nach Bedarf anpassen (Standardwerte funktionieren out of the box)
```

### Schritt 3: Datenbank starten
```bash
docker compose up -d
# Startet PostgreSQL im Hintergrund
# Warte ~5 Sekunden bis der Healthcheck grün ist
```

### Schritt 4: Python-Umgebung einrichten
```bash
python3 -m venv .venv
source .venv/bin/activate        # Mac/Linux
# .venv\Scripts\activate         # Windows

pip install -r etl-repository/requirements.txt
```

### Schritt 5: ETL ausführen
```bash
python etl-repository/src/etl.py
```

**Erwarteter Output:**
```
[EXTRACT] Fetching NBA season leaders from NBA API...
[EXTRACT] 231 players fetched.
[TRANSFORM] Cleaning and enriching data...
[TRANSFORM] Top player: Nikola Jokić (61.64 efficiency)
[LOAD] Writing to Postgres (DIH)...
[LOAD] 231 rows written to nba_player_stats.
[DONE] ETL pipeline completed successfully.
```

### Schritt 6: Daten prüfen
```bash
docker exec dih_postgres psql -U etl_user -d nba_dih \
  -c "SELECT player, team, pts, efficiency_score FROM nba_player_stats ORDER BY efficiency_score DESC LIMIT 10;"
```

### Aufräumen
```bash
docker compose down          # Container stoppen
docker compose down -v       # Container + Daten löschen
```

---

## Warum dieser Stack?

| Tool | Warum |
|------|-------|
| **Python + Polars** | Moderne, schnelle Datenverarbeitung — besser als Pandas für große Daten |
| **Docker** | "Runs everywhere" — keine "bei mir läuft's" Probleme mehr |
| **PostgreSQL** | Robuste, bewährte Open-Source-Datenbank — Industriestandard |
| **docker-compose** | Lokale Entwicklung mit mehreren Services einfach verwalten |
| **.env + .gitignore** | Secrets niemals in Git — Security Best Practice |

---

## Nächste Phasen (Roadmap)

| Phase | Was | Warum |
|-------|-----|-------|
| ✅ **Phase 1** | Lokales Setup | Fundament legen, Pipeline verstehen |
| 🔜 **Phase 2** | Docker Build & Run | ETL als Container lokal ausführen |
| 🔜 **Phase 3** | GitHub Actions (CI/CD) | Automatisch bauen & testen bei jedem Push |
| 🔜 **Phase 4** | Harbor (Container Registry) | Container-Images speichern & versionieren |
| 🔜 **Phase 5** | Kubernetes + Helm | In der Cloud deployen |
| 🔜 **Phase 6** | ArgoCD (GitOps) | Deployments automatisch aus Git synchronisieren |
| 🔜 **Phase 7** | Apache Airflow | Pipeline zeitgesteuert & orchestriert ausführen |

---

## Glossar für Non-Techies

| Begriff | Einfach erklärt |
|---------|-----------------|
| **ETL** | Extract-Transform-Load: Daten holen, aufbereiten, speichern |
| **Container** | Eine isolierte, portable "Fertig-Box" für Software |
| **Docker** | Das Tool zum Bauen und Starten von Containern |
| **PostgreSQL** | Eine Datenbank — wie Excel, aber für Millionen Zeilen und mehrere User |
| **API** | Eine Schnittstelle über die Programme miteinander sprechen (hier: NBA Statistiken) |
| **CI/CD** | Automatisches Testen und Deployen bei jedem Code-Push |
| **GitOps** | Der Git-Stand ist die einzige "Wahrheit" — was im Repo steht, läuft auch so |
| **Kubernetes** | Ein System das viele Container verwaltet — startet, überwacht, skaliert sie |
| **Helm** | Wie ein App-Store für Kubernetes — Pakete mit fertigen Kubernetes-Konfigurationen |
| **ArgoCD** | Überwacht das Git-Repo und synchronisiert Änderungen automatisch zu Kubernetes |
| **Airflow** | Ein Scheduler für Datenpipelines — "führe ETL jeden Tag um 6 Uhr aus" |
| **Harbor** | Eine private Docker-Registry — wie DockerHub, aber auf deinem eigenen Server |
| **Vault** | Ein Passwort-Safe für Server — speichert Secrets sicher und gibt sie kontrolliert raus |

---

*Gebaut mit Claude Code · Schritt für Schritt von lokal bis zur Cloud*
