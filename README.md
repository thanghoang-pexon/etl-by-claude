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

*Gebaut mit Claude Code · Schritt für Schritt von lokal bis zur Cloud*
