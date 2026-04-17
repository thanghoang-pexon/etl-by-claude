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
| ✅ **Phase 2** | Docker Build & Run | ETL als Container lokal ausführen |
| ✅ **Phase 3** | GitHub Actions (CI/CD) | Automatisch bauen & testen bei jedem Push |
| ✅ **Phase 4** | Harbor + Helm + ArgoCD | GitOps: Registry, Charts, automatisches Deployment |
| 🔜 **Phase 5** | Apache Airflow | Pipeline zeitgesteuert & orchestriert ausführen |
| 🔜 **Phase 6** | Azure Migration | Storage, Registry, Secrets in die Cloud |

---

## Phase 2: Docker Build & Run ✅

Jetzt führen wir den ETL nicht mehr direkt mit Python aus, sondern **als Container** —
genau so wie es später in der Cloud passieren wird.

### Das Networking-Problem (und die Lösung)

Wenn ein Container läuft, ist er standardmäßig isoliert — er kennt die Außenwelt nicht.
Unser ETL-Container muss aber mit dem Postgres-Container reden.

```
❌ Falsch: POSTGRES_HOST=localhost
   → "localhost" bedeutet innerhalb des Containers: ich selbst
   → Der ETL findet keine Datenbank

✅ Richtig: POSTGRES_HOST=dih_postgres  + gleiches Docker-Netzwerk
   → Container kennen sich gegenseitig beim Namen
   → Verbindung klappt
```

Docker Compose erstellt automatisch ein **virtuelles Netzwerk** für alle seine Services.
Wir hängen unseren ETL-Container einfach in dasselbe Netz.

```
┌─────────────────────────────────────────┐
│  Docker Netzwerk: etlbyclaude_default   │
│                                         │
│  [etl-nba Container] ──► [dih_postgres] │
│   (unser ETL)               (Datenbank) │
└─────────────────────────────────────────┘
```

### Image bauen

```bash
docker build -t etl-nba:local ./etl-repository
```

Was passiert hier?

- `docker build` = "Baue ein Image nach dem Bauplan"
- `-t etl-nba:local` = "Gib ihm den Namen `etl-nba` mit dem Tag `local`"
- `./etl-repository` = "Der Bauplan (Dockerfile) liegt in diesem Ordner"

**Was ist ein Tag?**
Tags sind Versionsnummern für Images. `local` bedeutet: mein lokaler Build.
Später werden wir Tags wie `1.0.0` oder `main-abc1234` (Git-Commit-Hash) verwenden.

### Container starten

```bash
docker run --rm \
  --env-file .env \
  -e POSTGRES_HOST=dih_postgres \
  --network etlbyclaude_default \
  etl-nba:local
```

Zeile für Zeile erklärt:

| Parameter | Bedeutung |
|-----------|-----------|
| `--rm` | Container nach dem Laufen automatisch löschen — wir brauchen ihn danach nicht mehr |
| `--env-file .env` | Alle Variablen aus `.env` in den Container laden |
| `-e POSTGRES_HOST=dih_postgres` | Eine einzelne Variable überschreiben (Host = Name des Postgres-Containers) |
| `--network etlbyclaude_default` | In dasselbe Netzwerk wie Postgres einhängen |
| `etl-nba:local` | Welches Image soll gestartet werden? |

### Warum `--rm`?

ETL-Container sind **kurzlebig** — sie starten, machen ihre Arbeit, hören auf.
Sie sind kein dauerhaft laufender Service wie Postgres.
`--rm` sorgt dafür, dass kein Container-Müll liegen bleibt.

### Was haben wir jetzt?

```
NBA API ──► [etl-nba:local Container] ──► [dih_postgres Container]
                  (ETL läuft)                   (Datenbank)
                  ↑
          docker run startet ihn,
          docker rm löscht ihn danach
```

Das ist der **vollständige lokale Pfad** aus der Architektur-Grafik:

```
ETL-Repository ──► Container (docker build/run) ──► DIH (PostgreSQL)
```

---

## Phase 3: CI/CD mit GitHub Actions ✅

Ab jetzt übernimmt GitHub die Arbeit. Jeder `git push` startet automatisch eine Pipeline.

### Was ist CI/CD?

| Begriff | Bedeutung | Beispiel hier |
|---------|-----------|---------------|
| **CI** – Continuous Integration | Jede Code-Änderung wird sofort automatisch getestet | Tests + DQ Checks laufen bei jedem Push |
| **CD** – Continuous Delivery | Gebaute Artefakte werden automatisch bereitgestellt | Docker Image landet in der Registry |

**Ohne CI/CD:** Du schreibst Code → du musst daran denken tests zu laufen → du baust das Image manuell → du pushst es irgendwo hin.

**Mit CI/CD:** Du schreibst Code → `git push` → alles andere passiert automatisch.

### Die Pipeline erklärt (`.github/workflows/ci.yml`)

```
git push
    │
    ▼
┌─────────────────────────────────────┐
│  JOB 1: test                        │
│  ├── Python 3.12 installieren       │
│  ├── Dependencies installieren      │
│  └── pytest -v (13 Tests)           │
│       ↓ nur wenn grün               │
└─────────────────────────────────────┘
    │ needs: test
    ▼ (nur auf main Branch)
┌─────────────────────────────────────┐
│  JOB 2: build-and-push              │
│  ├── Login zu ghcr.io               │
│  ├── docker build                   │
│  └── docker push → ghcr.io/...     │
│       Tag: main-abc1234 + latest    │
└─────────────────────────────────────┘
```

**Wichtige Prinzipien:**

**`needs: test`** — Job 2 wartet auf Job 1. Wenn Tests fehlschlagen, wird **kein** Image gebaut.
Das verhindert, dass kaputte Software in die Registry gelangt.

**`if: github.ref == 'refs/heads/main'`** — Images werden nur von `main` gebaut.
Feature-Branches laufen nur die Tests, bauen aber kein Image. Spart Registry-Speicher.

**`GITHUB_TOKEN`** — GitHub stellt automatisch ein temporäres Token bereit, das nur für
diesen Pipeline-Lauf gültig ist. Du musst kein Passwort hinterlegen.

### Was ist die GitHub Container Registry (ghcr.io)?

Eine Container-Registry ist ein Lager für Docker-Images — wie npm für JavaScript-Pakete
oder PyPI für Python-Pakete, nur eben für Container.

```
ghcr.io/thanghoang-pexon/etl-by-claude/etl-nba:main-abc1234
│        │                              │        │
Registry  GitHub-User                  Image    Version (Git-SHA)
```

**Warum Git-SHA als Tag?**
Jeder Commit hat einen eindeutigen Hash (z.B. `abc1234`). Wenn ein Image mit diesem
Tag gebaut wird, kannst du jederzeit exakt nachvollziehen welcher Code darin steckt.
Das ist die Grundlage für **reproduzierbare Deployments**.

### Data Quality Checks im ETL

Zwischen Transform und Load läuft jetzt eine `validate()` Funktion:

```python
# src/validate.py — was wird geprüft?
✓ Mindestens 100 Spieler (Vollständigkeit)
✓ Keine doppelten player_ids (Eindeutigkeit)
✓ Keine Nullwerte in Pflichtfeldern (Vollständigkeit)
✓ Punkte ≥ 0 (Wertebereich)
✓ Prozentwerte zwischen 0 und 1 (Wertebereich)
✓ Efficiency Score berechnet (Berechnungsqualität)
```

Wenn ein Check fehlschlägt: Pipeline stoppt, **keine** Daten landen in der Datenbank.
Das ist das "fail fast" Prinzip — lieber früh einen Fehler werfen als falsche Daten speichern.

---

## Phase 4: Harbor + Helm + ArgoCD ✅

Das ist der Kern des GitOps-Stacks. Drei neue Werkzeuge — jedes mit einer klaren Aufgabe.

---

### Was ist Helm?

Stell dir vor, du willst PostgreSQL in Kubernetes deployen. Das sind allein schon ~5 YAML-Dateien
(Deployment, Service, PVC, Secret, ConfigMap). Wenn du das für 10 verschiedene Umgebungen brauchst
(dev, staging, prod), kopierst du diese Dateien 10 Mal — mit kleinen Unterschieden überall.

**Helm löst das:** Ein **Helm Chart** ist eine parametrisierbare Vorlage.

```
helm install mein-etl ./ops-repository/helm/etl-stack \
  --set postgres.password=geheim \
  --set etl.image.tag=v1.2.3
```

```
ops-repository/helm/etl-stack/
├── Chart.yaml        ← Name, Version, Beschreibung
├── values.yaml       ← Standardwerte (überschreibbar per --set oder -f)
└── templates/        ← YAML-Vorlagen mit {{ .Values.xxx }} Platzhaltern
    ├── postgres-deployment.yaml
    ├── postgres-service.yaml
    ├── postgres-pvc.yaml
    ├── postgres-secret.yaml
    └── etl-job.yaml   ← ETL läuft als Kubernetes Job (einmalig, kein Dauerbetrieb)
```

**Warum `Job` statt `Deployment`?**
Ein `Deployment` hält Pods dauerhaft am Laufen (z.B. ein Webserver).
Ein `Job` startet, führt eine Aufgabe aus, und endet — perfekt für ETL.
Später steuert Airflow wann dieser Job läuft.

---

### Was ist Harbor?

Harbor ist eine **private Container-Registry** — wie DockerHub, aber auf deinem eigenen Server.

| Feature | DockerHub | ghcr.io | Harbor |
|---------|-----------|---------|--------|
| Kostenlos | ✓ (eingeschränkt) | ✓ | Self-hosted |
| Privat | ✓ (kostenpflichtig) | ✓ | ✓ |
| Web-UI | ✓ | minimal | ✓ vollständig |
| Vulnerability Scanning | ✗ | ✗ | ✓ (Trivy) |
| RBAC | ✗ | ✗ | ✓ |
| Replication | ✗ | ✗ | ✓ |

```
Installation via Helm (1 Befehl, ~8 Services werden gestartet):

helm repo add harbor https://helm.goharbor.io
helm install harbor harbor/harbor \
  --namespace harbor --create-namespace \
  --set expose.type=nodePort \
  --set expose.tls.enabled=false \
  --set expose.nodePort.ports.http.nodePort=30080 \
  --set externalURL=http://$(minikube ip):30080 \
  --set harborAdminPassword=Harbor12345 \
  --set persistence.enabled=false
```

**Harbor Web-UI:** `http://$(minikube ip):30080` · User: `admin` · PW: `Harbor12345`

---

### Was ist ArgoCD?

ArgoCD ist ein **GitOps-Operator** — er lebt im Cluster und überwacht dein Git-Repo.

```
┌─────────────────────────────────────────────────────────┐
│  Ohne GitOps:                                           │
│  Du → kubectl apply → Cluster                          │
│  Problem: Wer hat wann was deployed? Undokumentiert.   │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  Mit GitOps (ArgoCD):                                   │
│  Du → git push → GitHub → ArgoCD erkennt Änderung      │
│                          → kubectl apply (automatisch) │
│  Vorteil: Git = einzige Quelle der Wahrheit             │
└─────────────────────────────────────────────────────────┘
```

**ArgoCD Application** (in `ops-repository/argocd/application.yaml`):
```yaml
source:
  repoURL: https://github.com/thanghoang-pexon/etl-by-claude.git
  path: ops-repository/helm/etl-stack   # ← diesen Pfad überwachen

destination:
  namespace: etl                         # ← hier deployen

syncPolicy:
  automated:
    selfHeal: true   # manuelle kubectl-Änderungen werden zurückgesetzt
    prune: true      # gelöschte Ressourcen im Repo = gelöscht im Cluster
```

---

### Der vollständige GitOps-Flow

```
1. Du schreibst ETL-Code
       │
       ▼
2. git push → GitHub
       │
       ▼
3. GitHub Actions:
   ├── Tests laufen (pytest)
   ├── Docker Image wird gebaut
   ├── Image nach ghcr.io gepusht (Tag: main-abc1234)
   └── values.yaml wird automatisch aktualisiert:
       tag: main-abc1234   [skip ci]
       └─► git commit + push
       │
       ▼
4. ArgoCD erkennt Änderung in ops-repository/helm/etl-stack/values.yaml
       │
       ▼
5. ArgoCD deployed automatisch:
   ├── PostgreSQL läuft als Deployment im Namespace "etl"
   └── ETL Job startet mit dem neuen Image
       │
       ▼
6. Daten landen in PostgreSQL (DIH)
```

**Das Elegante:** Du musst nach `git push` nichts mehr tun.
Der gesamte Weg vom Code bis zur laufenden Pipeline ist automatisiert.

---

### Setup ausführen

```bash
# 1. Cluster (minikube bereits laufend)
kubectl cluster-info

# 2. ArgoCD installieren
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# 3. Harbor installieren
helm repo add harbor https://helm.goharbor.io
helm install harbor harbor/harbor --namespace harbor --create-namespace \
  --set expose.type=nodePort --set expose.tls.enabled=false \
  --set expose.nodePort.ports.http.nodePort=30080 \
  --set externalURL=http://$(minikube ip):30080 \
  --set harborAdminPassword=Harbor12345 --set persistence.enabled=false

# 4. ArgoCD Application deployen
kubectl apply -f ops-repository/argocd/application.yaml

# 5. UIs öffnen
bash scripts/open-uis.sh
```

### UIs

| Tool | URL | User | Passwort |
|------|-----|------|----------|
| ArgoCD | http://localhost:8080 | admin | `kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" \| base64 -d` |
| Harbor | http://$(minikube ip):30080 | admin | Harbor12345 |

### Image für lokales Testing laden (ohne CI)

```bash
bash scripts/load-local-image.sh
# Baut Image lokal, lädt es in minikube, setzt values.yaml auf lokales Image
```

### ⚠️ Wichtig: ghcr.io Package öffentlich machen

Damit ArgoCD/Kubernetes das Image von ghcr.io pullen kann ohne Credentials:
1. GitHub → Dein Profil → Packages → `etl-nba` → Package Settings
2. "Change visibility" → Public

Alternativ: `imagePullSecret` in values.yaml konfigurieren (für private Registries).

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

## Der vollständige Flow — Gesamtüberblick

### Wie wird die Pipeline getriggert?

**Aktuell (Phase 1–4):** Die Pipeline läuft nur wenn Code gepusht wird.
**Ab Phase 5 (Airflow):** Die Pipeline läuft zeitgesteuert — unabhängig von Code-Änderungen.

Das ist der zentrale Unterschied:

```
TRIGGER HEUTE:         git push → CI → Image → ArgoCD → K8s Job läuft einmal

TRIGGER AB PHASE 5:   Airflow Scheduler (täglich 06:00) → K8s Job
                      ODER: Airflow UI → "Trigger DAG" (manuell)
                      ODER: Airflow REST API → von außen angesteuert
```

### Was passiert bei einem git push (aktueller vollständiger Flow)?

```
git push to main
        │
        ▼
┌───────────────────────────────────────────────────────────┐
│  GITHUB ACTIONS                                           │
│                                                           │
│  Job 1: test                                              │
│  ├─ pytest (16 Tests)                                     │
│  └─ nur wenn grün → weiter                                │
│                                                           │
│  Job 2: build-and-push         (nur auf main)             │
│  ├─ docker build                                          │
│  └─ push → ghcr.io :main-abc1234 + :latest               │
│                                                           │
│  Job 3: update-ops-repo        (nach Job 2)               │
│  ├─ values.yaml: tag = main-abc1234                       │
│  └─ git commit [skip ci] + push                           │
└───────────────────────────────────────────────────────────┘
        │
        │  values.yaml hat sich geändert
        ▼
┌───────────────────────────────────────────────────────────┐
│  ARGOCD                                                   │
│  ├─ Erkennt Änderung im GitHub Repo (polling alle 3 Min)  │
│  ├─ helm upgrade etl-stack                                │
│  └─ Erstellt neuen Kubernetes Job                         │
└───────────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────────┐
│  KUBERNETES JOB (einmalig, danach fertig)                 │
│  ├─ init-container: wartet bis Postgres ready             │
│  ├─ runner.py liest PIPELINE=nba_stats                    │
│  ├─ NbaStatsPipeline.extract()   → NBA API                │
│  ├─ NbaStatsPipeline.transform() → Polars                 │
│  ├─ NbaStatsPipeline.validate()  → DQ-Checks              │
│  └─ db.load()                    → PostgreSQL (DIH)       │
└───────────────────────────────────────────────────────────┘
```

### Wer ist für was zuständig?

| Schicht | Tool | Frage die es beantwortet |
|---------|------|--------------------------|
| Code-Qualität | pytest + DQ-Checks | Ist der Code korrekt und die Daten valide? |
| CI/CD | GitHub Actions | Wie kommt Code als versioniertes Image in die Registry? |
| Image-Registry | ghcr.io / Harbor | Wo sind alle Image-Versionen gespeichert? |
| Deployment | ArgoCD + Helm | Welche Version läuft wo im Cluster? |
| Scheduling | **Airflow** (Phase 5) | Wann läuft die Pipeline? Mit welchen Parametern? |
| Secrets | .env → Vault (Phase 6) | Wer darf auf welche Credentials zugreifen? |
| Cloud | Azure (Phase 6) | Wo laufen Datenbank, Registry, Cluster produktiv? |

### Die wichtige Trennung

```
Code-Änderung  ──────────────►  neues Image bauen  (GitHub Actions)
                                       ≠
Neue Daten verfügbar  ──────►  Pipeline ausführen   (Airflow, Phase 5)
```

Diese Trennung ist der Kern von produktionsreifem Data Engineering.
Ohne sie läuft die Pipeline nur wenn Entwickler Code schreiben — nicht wenn Daten kommen.

### Neue Pipeline hinzufügen (Plugin-Architektur)

```python
# 1. Datei anlegen: etl-repository/src/pipelines/weather.py
class WeatherPipeline(BasePipeline):
    @property
    def name(self): return "weather"

    def extract(self): ...      # open-meteo API, CSV, DB — beliebige Quelle
    def transform(self, df): ... # nur diese Methode ändern sich pro Datensatz

# 2. Registrieren: src/pipelines/__init__.py
REGISTRY = {
    "nba_stats": NbaStatsPipeline,
    "weather":   WeatherPipeline,  # ← das wars
}

# 3. Deployment: ops-repository/helm/etl-stack/values.yaml
etl:
  pipeline: weather  # ← ArgoCD deployed automatisch
```

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
| **DAG** | Directed Acyclic Graph — Airflow-Begriff für eine Pipeline mit definierten Schritten |
| **Plugin-Architektur** | System das durch neue Dateien erweiterbar ist, ohne bestehenden Code zu ändern |

---

## Technologie-Stack & Austausch-Guide

Jede Komponente dieses Stacks ist bewusst austauschbar gehalten.
Die Tabellen zeigen was wir nutzen, warum — und wann du es ersetzen würdest.

---

### Datenverarbeitung (Transform-Schicht)

| Aktuell | Warum gewählt | Ersetzen durch | Wann sinnvoll |
|---------|---------------|----------------|---------------|
| **Polars** | Schnell, modernes API, kein Java | **Pandas** | Wenn viele Bibliotheken Pandas voraussetzen |
| **Polars** | Läuft auf einem einzelnen Rechner | **PySpark** | Wenn Daten nicht mehr in RAM passen (> 10 GB) |
| **Polars** | Python-Code, flexibel | **dbt** | Wenn Transformationen SQL-basiert sein sollen und Analysten sie pflegen |
| **Polars** | Eigene Logik | **DuckDB** | Wenn SQL-Analytik direkt auf Parquet/CSV-Dateien ohne Datenbank nötig |

**Austausch in diesem Projekt:** Nur `transform()` in der jeweiligen Pipeline-Klasse ändern.
`runner.py`, `db.py` und die gesamte Infrastruktur bleiben unberührt.

```python
# PySpark-Beispiel — gleiche Schnittstelle, anderer Code
class NbaSparkPipeline(BasePipeline):
    def transform(self, df: pl.DataFrame) -> pl.DataFrame:
        spark_df = spark.createDataFrame(df.to_pandas())
        spark_df = spark_df.withColumn("efficiency", ...)
        return pl.from_pandas(spark_df.toPandas())
```

---

### Verarbeitungsmodus (Batch vs. Streaming)

| Aktuell | Warum gewählt | Ersetzen durch | Wann sinnvoll |
|---------|---------------|----------------|---------------|
| **Batch (täglich)** | Einfach, NBA-Daten ändern sich langsam | **Apache Kafka + Flink** | Wenn Daten in Echtzeit fließen (Klick-Events, Sensoren) |
| **Batch** | Kein Streaming-Overhead | **Azure Event Hubs** | Managed Kafka-Alternative in Azure |
| **Batch** | Einfach zu debuggen | **Spark Structured Streaming** | Wenn PySpark ohnehin genutzt wird und Near-Realtime reicht |

**Konzept-Unterschied:**

```
Batch:     [alle Daten] → verarbeiten → Ergebnis  (1x täglich)
Streaming: Daten fließen → jedes Event sofort verarbeiten → Ergebnis in ms
```

Für die meisten Data-Engineering-Anwendungsfälle ist Batch die richtige Wahl.
Streaming ist komplexer, teurer und nur dann nötig wenn Sekunden zählen.

---

### Datenspeicher (Load-Schicht / DIH)

| Aktuell | Warum gewählt | Ersetzen durch | Wann sinnvoll |
|---------|---------------|----------------|---------------|
| **PostgreSQL** | Einfach, lokal, kein Vendor-Lock-in | **Azure Database for PostgreSQL** | Managed PostgreSQL in Azure, kein Ops-Aufwand |
| **PostgreSQL** | Strukturierte Daten, SQL | **Azure Blob Storage** (Data Lake) | Wenn Rohdaten als Parquet/CSV archiviert werden sollen |
| **PostgreSQL** | Zeilenbasiert | **Azure Synapse Analytics** | Wenn sehr große Mengen für BI-Reports (Spalten-optimiert) |
| **PostgreSQL** | On-premise | **Snowflake** | Cloud-natives Data Warehouse, einfach zu skalieren |
| **PostgreSQL** | Einfaches Schema | **Delta Lake** | Wenn ACID-Transaktionen + Versionierung auf dem Data Lake nötig |

**Austausch in diesem Projekt:** Nur `db.py` + `create_table_sql()` in der Pipeline anpassen.
Die Transformationslogik bleibt komplett unverändert.

```python
# Azure Blob Storage Beispiel — db.py ersetzen
def load(df: pl.DataFrame, table_name: str, **_) -> None:
    from azure.storage.blob import BlobServiceClient
    client = BlobServiceClient.from_connection_string(os.environ["AZURE_STORAGE_CONN"])
    blob = client.get_blob_client("etl-data", f"{table_name}.parquet")
    blob.upload_blob(df.write_parquet(None), overwrite=True)
```

---

### Container-Registry

| Aktuell | Warum gewählt | Ersetzen durch | Wann sinnvoll |
|---------|---------------|----------------|---------------|
| **ghcr.io** | Kostenlos, direkt bei GitHub | **Harbor** (self-hosted) | Wenn RBAC, Vulnerability Scanning, kein Vendor-Lock-in nötig |
| **ghcr.io** | Einfach für CI | **Azure Container Registry (ACR)** | Wenn Stack auf Azure liegt — nahtlose AKS-Integration |
| **ghcr.io** | Open | **AWS ECR / GCR** | Bei AWS/GCP-Stack |

**Austausch:** Nur `ci.yml` — Login-Schritt und Image-URL ändern.
Helm-Chart, ArgoCD, Kubernetes bleiben unverändert.

```yaml
# ACR statt ghcr.io — nur diese Zeilen in ci.yml ändern:
- uses: docker/login-action@v3
  with:
    registry: myregistry.azurecr.io
    username: ${{ secrets.ACR_USERNAME }}
    password: ${{ secrets.ACR_PASSWORD }}
```

---

### CI/CD

| Aktuell | Warum gewählt | Ersetzen durch | Wann sinnvoll |
|---------|---------------|----------------|---------------|
| **GitHub Actions** | Direkt in GitHub, kein Extra-Tool | **GitLab CI** | Wenn das Unternehmen GitLab nutzt (Self-hosted) |
| **GitHub Actions** | YAML-basiert, einfach | **Azure DevOps Pipelines** | Vollständige Azure-Integration mit Boards, Repos |
| **GitHub Actions** | Kostenlos für public | **Tekton** | K8s-native CI/CD — alles läuft im Cluster |
| **GitHub Actions** | Managed | **Jenkins** | Maximale Flexibilität, aber viel Ops-Aufwand |

**Konzept-Transfer:** GitHub Actions und GitLab CI sind fast identisch.
Ein GitHub-Actions-Workflow lässt sich in ~30 Minuten zu GitLab CI migrieren.

---

### Kubernetes & Deployment

| Aktuell | Warum gewählt | Ersetzen durch | Wann sinnvoll |
|---------|---------------|----------------|---------------|
| **minikube** (lokal) | Bereits vorhanden, einfach | **kind** | Leichter, CI-freundlicher (wenn kind-Boot-Probleme gelöst) |
| **minikube** (lokal) | Für Entwicklung | **Azure AKS** | Produktions-Kubernetes in Azure, managed |
| **minikube** (lokal) | Lokal | **k3s** | Leichtgewichtig, gut für Edge/IoT |
| **Helm** | Industrie-Standard | **Kustomize** | Wenn nur YAML-Overlays ohne Templating nötig |
| **ArgoCD** | Beste UI, weit verbreitet | **Flux CD** | Leichtgewichtiger, kein UI aber GitOps-konform |

---

### Scheduling & Orchestrierung

| Aktuell | Warum gewählt | Ersetzen durch | Wann sinnvoll |
|---------|---------------|----------------|---------------|
| **(geplant) Airflow** | Marktführer, K8s-nativ | **Prefect** | Moderner Python-First, bessere UX |
| **(geplant) Airflow** | Open Source | **Dagster** | Asset-basiertes Denken, starkes Lineage-Feature |
| **(geplant) Airflow** | Self-hosted | **Azure Data Factory** | Managed, No-Code-Pipelines für Azure-Ökosystem |
| **(geplant) Airflow** | Flexibel | **AWS Glue** | Managed Spark-Jobs auf AWS |

---

### Secrets Management

| Aktuell | Warum gewählt | Ersetzen durch | Wann sinnvoll |
|---------|---------------|----------------|---------------|
| **.env** (lokal) | Einfachst möglich, klar verständlich | **HashiCorp Vault** | Self-hosted, feingranulare Zugriffssteuerung |
| **.env** (lokal) | Kein Extra-Service | **Azure Key Vault** | Managed, perfekte AKS-Integration über Workload Identity |
| **.env** (lokal) | Transparent | **K8s Secrets + External Secrets Operator** | Secrets in K8s nativ, aus Vault/Azure Key Vault synchronisiert |

---

### Data Quality

| Aktuell | Warum gewählt | Ersetzen durch | Wann sinnvoll |
|---------|---------------|----------------|---------------|
| **Eigene Polars-Checks** | Kein Extra-Dependency, transparent | **Great Expectations** | Wenn DQ-Checks dokumentiert und geteilt werden sollen |
| **Eigene Checks** | Einfach zu erweitern | **Soda Core** | Wenn DQ-Checks als YAML konfiguriert (nicht code) werden sollen |
| **Eigene Checks** | Leichtgewichtig | **Pandera** | Schema-Validierung mit Pandas/Polars-Integration |
| **Eigene Checks** | Manuell definiert | **dbt tests** | Wenn dbt ohnehin für Transformationen genutzt wird |

---

### Übersicht: Austausch-Aufwand

```
Niedrig (nur 1-2 Dateien ändern):
  Datenverarbeitung   → transform() in Pipeline-Klasse
  Datenspeicher       → db.py + create_table_sql()
  Container-Registry  → ci.yml Login + Image-URL

Mittel (Konfiguration + 1 Service tauschen):
  CI/CD               → .github/workflows/ → .gitlab-ci.yml
  Secrets             → .env → Vault → Azure Key Vault
  Orchestrierung      → Airflow DAG → Prefect Flow

Hoch (Infrastruktur-Änderung):
  Kubernetes          → minikube → AKS (Cluster neu provisionieren)
  Batch → Streaming   → Komplettes Pipeline-Pattern ändern
  SQL → Data Lake     → Storage-Layer + Query-Engine ersetzen
```

---

*Gebaut mit Claude Code · Schritt für Schritt von lokal bis zur Cloud*
