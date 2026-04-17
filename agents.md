# agents.md — Vollständiges Build-Rezept

Dieses Dokument beschreibt den kompletten Stack von Null auf.
Ein Agent oder Entwickler der dieses Dokument liest soll in der Lage sein,
das gesamte Projekt exakt zu reproduzieren — ohne weitere Kontextinformationen.

---

## Projektziel

Einen produktionsnahen, modularen **GitOps-ETL-Stack** aufbauen:
- ETL-Pipelines in Python (Polars) mit Plugin-Architektur
- Vollautomatische CI/CD via GitHub Actions
- Container-Images in Harbor (self-hosted Registry)
- Kubernetes-Deployment via Helm Charts
- GitOps-Automatisierung via ArgoCD
- Scheduling via Apache Airflow (Phase 5)
- Secrets via HashiCorp Vault / .env (Phase 6)
- Azure Cloud Migration (Phase 6)

**Kernprinzip:** Code-Änderung und Daten-Scheduling sind strikt getrennt.
Code pushen → neues Image. Neue Daten → Airflow-Scheduler.

**Lernprojekt:** Jede Komponente ist bewusst austauschbar gehalten.
Heute lokale Postgres → morgen Azure PostgreSQL. Nur `values.yaml` ändern.

---

## Stack-Entscheidungen

| Komponente | Gewählt | Alternativen | Begründung |
|------------|---------|--------------|------------|
| ETL-Sprache | Python + Polars | PySpark, Pandas | Modern, schnell, einfach zu erklären |
| Container-Runtime | Docker | Podman | Verbreitet, gut dokumentiert |
| CI/CD | GitHub Actions | GitLab CI | Bereits auf GitHub, keine Migration |
| Container-Registry | ghcr.io → Harbor | Docker Hub, ACR | ghcr.io für CI kostenlos, Harbor self-hosted |
| K8s lokal | minikube | kind, k3s | Bereits laufend, kind hatte Boot-Probleme |
| Deployment | Helm + ArgoCD | Kustomize, Flux | Helm = Industry Standard, ArgoCD = beste GitOps-UI |
| Datenbank | PostgreSQL | MySQL, SQLite | Robust, Open Source, Azure-kompatibel |
| Secrets | .env → Vault | AWS Secrets Manager | .env für Einstieg, Vault für Produktion |
| Scheduler | Apache Airflow | Prefect, Dagster | Marktführer, K8s-native mit KubernetesExecutor |

---

## Voraussetzungen (lokal installieren)

```bash
# Pflicht
brew install docker       # oder Docker Desktop
brew install git
brew install kubectl
brew install helm
brew install minikube     # ODER kind (kind hatte bei uns Probleme mit K8s 1.35+)

# Optional aber empfohlen
brew install gh           # GitHub CLI für Repo-Management
```

**Python-Version:** 3.10+ (getestet mit 3.9 lokal, 3.12 im Container)

---

## Projektstruktur (vollständig)

```
etl-by-claude/
├── .env                          # Lokale Secrets — NIEMALS nach GitHub!
├── .env.example                  # Vorlage ohne echte Werte — darf ins Repo
├── .gitignore                    # .env, __pycache__, .venv
├── docker-compose.yml            # Lokale Postgres-Instanz (DIH)
├── kind-config.yml               # K8s-Cluster-Config (kind, alternativ zu minikube)
├── agents.md                     # Dieses Dokument
├── README.md                     # Nutzer-Dokumentation, Phase für Phase
│
├── etl-repository/               # ETL-Code (wird separates Git-Repo)
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── pyproject.toml            # pytest-Konfiguration
│   └── src/
│       ├── runner.py             # Universeller Entrypoint (liest PIPELINE env var)
│       ├── db.py                 # Generische DB-Operationen (load, get_conn)
│       ├── validate.py           # Generische DQ-Checks
│       └── pipelines/
│           ├── __init__.py       # REGISTRY + get_pipeline()
│           ├── base.py           # BasePipeline ABC
│           └── nba_stats.py      # NBA-spezifische Pipeline
│   └── tests/
│       └── test_transform.py     # 16 Tests: Transform, DQ, Registry
│
├── ops-repository/               # Deployment-Konfigurationen (wird separates Git-Repo)
│   ├── helm/
│   │   └── etl-stack/
│   │       ├── Chart.yaml
│   │       ├── values.yaml       # ← GitHub Actions updated hier den Image-Tag
│   │       └── templates/
│   │           ├── _helpers.tpl
│   │           ├── postgres-secret.yaml
│   │           ├── postgres-pvc.yaml
│   │           ├── postgres-deployment.yaml
│   │           ├── postgres-service.yaml
│   │           └── etl-job.yaml  # ETL als K8s Job (kein Deployment)
│   └── argocd/
│       └── application.yaml      # ArgoCD Application-Definition
│
├── scripts/
│   ├── setup-cluster.sh          # kind + lokale Registry aufsetzen
│   ├── open-uis.sh               # ArgoCD + Harbor im Browser öffnen
│   └── load-local-image.sh       # Image in minikube laden (ohne CI)
│
└── .github/
    └── workflows/
        └── ci.yml                # 3-Job-Pipeline: test → build-push → gitops-update
```

---

## Phase 1: Lokales Setup

### Was entsteht
- PostgreSQL lokal via Docker Compose (der "DIH" aus der Architektur-Grafik)
- Python ETL-Code der gegen diese Datenbank schreibt
- Secrets via `.env`-Datei

### Schritt-für-Schritt

**1. Verzeichnisstruktur anlegen**
```bash
mkdir etl-by-claude && cd etl-by-claude
mkdir -p etl-repository/src etl-repository/tests scripts .github/workflows
```

**2. `.gitignore` anlegen**
```
.env
__pycache__/
*.pyc
.venv/
```

**3. `.env` anlegen** (wird nicht gepusht)
```env
POSTGRES_USER=etl_user
POSTGRES_PASSWORD=etl_password
POSTGRES_DB=nba_dih
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
```

**4. `.env.example` anlegen** (wird gepusht, ohne echte Werte)
```env
POSTGRES_USER=etl_user
POSTGRES_PASSWORD=etl_password
POSTGRES_DB=nba_dih
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
```

**5. `docker-compose.yml` anlegen**
```yaml
services:
  postgres:
    image: postgres:16-alpine
    container_name: dih_postgres
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
```

**6. `etl-repository/requirements.txt`**
```
nba_api==1.4.1
polars==1.30.0
psycopg[binary]==3.2.4
python-dotenv==1.0.1
pytest==8.3.5
```

**⚠️ Wichtig macOS:** `psycopg2-binary` funktioniert auf macOS ARM nicht (libpq fehlt).
Stattdessen `psycopg[binary]==3.2.4` (psycopg3) verwenden.
DB-URL-Prefix: `postgresql+psycopg://` statt `postgresql+psycopg2://`.

**7. Python-Umgebung**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r etl-repository/requirements.txt
```

**8. Postgres starten + testen**
```bash
docker compose up -d
docker compose ps  # Status: healthy
```

### Datensatz-Wahl: NBA API

Wir nutzen `nba_api` — kostenlos, kein API-Key, reiche Daten.

```python
from nba_api.stats.endpoints import leagueleaders
response = leagueleaders.LeagueLeaders(season="2024-25", ...)
# Liefert ~231 Spieler mit Stats (Punkte, Assists, Rebounds, etc.)
```

**Eigener Metric:** `efficiency_score = pts + ast*1.5 + reb*1.2 + stl*2 + blk*2 - tov`

---

## Phase 2: Docker Build & Run

### Was entsteht
- ETL läuft als Container (nicht mehr direkt mit Python)
- Docker-Networking-Konzept verstanden

### Dockerfile

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ ./src/
CMD ["python", "src/runner.py"]
```

**Layer-Reihenfolge:** `requirements.txt` VOR `src/` kopieren → Docker cached Pakete
solange sich requirements nicht ändert. Nur Code-Änderungen bauen schnell.

### Lokaler Run (Container gegen Postgres)

```bash
# Image bauen
docker build -t etl-nba:local ./etl-repository

# Container starten
# POSTGRES_HOST muss der Container-Name sein, nicht "localhost"!
docker run --rm \
  --env-file .env \
  -e POSTGRES_HOST=dih_postgres \
  --network etlbyclaude_default \
  etl-nba:local
```

**Networking-Regel:** `localhost` inside Container = der Container selbst.
Für Container-zu-Container-Kommunikation: gleicher Docker-Network + Service-Name als Host.

---

## Phase 3: CI/CD mit GitHub Actions

### Was entsteht
- 3-Job-Pipeline die bei jedem `git push` startet
- Images landen versioniert in ghcr.io
- `values.yaml` wird automatisch mit neuem Tag updated

### `.github/workflows/ci.yml` — Aufbau

```
Job 1: test
  - python:3.12 setup
  - pip install
  - pytest -v
  → Nur wenn grün: Job 2

Job 2: build-and-push  (nur auf main)
  - Login zu ghcr.io mit GITHUB_TOKEN
  - docker/metadata-action → Tags: main-{sha7} + latest
  - docker/build-push-action mit GitHub Actions Cache
  → Immer nach Job 2: Job 3

Job 3: update-ops-repo
  - git rev-parse --short HEAD → SHORT_SHA
  - sed -i "s|tag: .*|tag: main-{SHA}|" ops-repository/helm/etl-stack/values.yaml
  - git commit -m "ci: update tag [skip ci]"
  - git push
```

**`[skip ci]`** im Commit-Message verhindert Pipeline-Loop (GitHub respektiert das).

**Permissions:**
- `packages: write` — für ghcr.io Push
- `contents: write` — für den Git-Commit zurück ins Repo

### Image-Tags

```
ghcr.io/thanghoang-pexon/etl-by-claude/etl-nba:main-abc1234  ← exakter Commit
ghcr.io/thanghoang-pexon/etl-by-claude/etl-nba:latest        ← immer aktuellstes
```

**Warum Git-SHA als Tag?** Reproduzierbarkeit. Zu jedem laufenden Container
gibt es einen exakten Commit-Hash → `git checkout abc1234` zeigt genau den Code.

---

## Phase 4: Harbor + Helm + ArgoCD

### Was entsteht
- Lokaler Kubernetes-Cluster (minikube)
- Harbor Container-Registry via Helm
- ArgoCD GitOps-Operator
- Helm Chart für ETL-Stack
- Vollautomatischer GitOps-Flow

### Cluster Setup

```bash
# minikube starten (ODER kind — siehe Probleme unten)
minikube start
kubectl get nodes  # sollte Ready zeigen
```

**⚠️ kind-Problem:** Bei kind v0.31.0 + K8s v1.35.0 schlägt `kubeadm init` fehl
wenn minikube parallel läuft (Ressourcen-Konflikt). Lösung: minikube nutzen.

### ArgoCD installieren

```bash
kubectl create namespace argocd
kubectl apply -n argocd \
  -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Warten bis bereit
kubectl -n argocd rollout status deployment/argocd-server --timeout=120s

# Admin-Passwort
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d
```

**ArgoCD UI:** `kubectl port-forward svc/argocd-server -n argocd 8080:443`
→ `http://localhost:8080` · User: `admin`

### Harbor installieren (via Helm)

```bash
helm repo add harbor https://helm.goharbor.io
helm repo update

helm install harbor harbor/harbor \
  --namespace harbor --create-namespace \
  --set expose.type=nodePort \
  --set expose.tls.enabled=false \
  --set expose.nodePort.ports.http.nodePort=30080 \
  --set externalURL=http://$(minikube ip):30080 \
  --set harborAdminPassword=Harbor12345 \
  --set persistence.enabled=false
```

**Harbor UI:** `http://$(minikube ip):30080` · User: `admin` · PW: `Harbor12345`

**Warum Harbor?** Private Registry mit Web-UI, RBAC, Vulnerability Scanning (Trivy),
Image-Replication. Für Produktion: auf AKS deployen oder Azure Container Registry nutzen.

### Helm Chart Struktur

```
ops-repository/helm/etl-stack/
├── Chart.yaml          → name: etl-stack, version: 0.1.0
├── values.yaml         → alle Standardwerte (überschreibbar)
└── templates/
    ├── _helpers.tpl              → gemeinsame Labels
    ├── postgres-secret.yaml      → K8s Secret aus values
    ├── postgres-pvc.yaml         → 1Gi PersistentVolumeClaim
    ├── postgres-deployment.yaml  → Deployment mit readinessProbe
    ├── postgres-service.yaml     → ClusterIP Service auf Port 5432
    └── etl-job.yaml              → K8s Job mit init-container
```

**Warum K8s Job (kein Deployment)?**
ETL ist ein einmaliger Prozess: starten → arbeiten → fertig.
Ein Deployment würde dauerhaft laufen und neustarten — falsch für ETL.
Jobs sind "fire-and-forget", Airflow erstellt sie später on-demand.

**init-container im etl-job.yaml:**
```yaml
initContainers:
  - name: wait-for-postgres
    image: busybox
    command: ["sh", "-c", "until nc -z postgres 5432; do sleep 2; done"]
```
Stellt sicher: Postgres ist ready bevor ETL startet. Ohne das: Race Condition.

### ArgoCD Application

```yaml
# ops-repository/argocd/application.yaml
spec:
  source:
    repoURL: https://github.com/thanghoang-pexon/etl-by-claude.git
    path: ops-repository/helm/etl-stack
  destination:
    namespace: etl
  syncPolicy:
    syncOptions:
      - CreateNamespace=true
    automated:
      selfHeal: true   # manuelle kubectl-Änderungen werden zurückgesetzt
      prune: true      # Ressourcen die im Repo gelöscht werden, werden auch im Cluster gelöscht
```

```bash
kubectl apply -f ops-repository/argocd/application.yaml
```

### Vollständiger GitOps-Flow

```
git push to main
        ↓
GitHub Actions Job 1: Tests grün?
        ↓ ja
Job 2: docker build + push → ghcr.io:main-{sha}
        ↓
Job 3: sed values.yaml tag=main-{sha} + git commit [skip ci]
        ↓
ArgoCD erkennt values.yaml-Änderung (polling alle 3 Min)
        ↓
helm upgrade → neuer K8s Job wird erstellt
        ↓
K8s Job: runner.py → extract → transform → validate → load → PostgreSQL
```

**⚠️ ghcr.io Image muss öffentlich sein** damit K8s ohne Credentials pullen kann:
GitHub → Packages → etl-nba → Package Settings → Change visibility → Public

Alternativ: imagePullSecret in values.yaml konfigurieren.

---

## Phase 4.5: Plugin-Architektur (universelle Pipelines)

### Problem
Monolithischer ETL-Code: NBA-Logik und Infrastruktur vermischt.
Neue Datenquelle = Code-Änderungen überall.

### Lösung: BasePipeline + Registry

```python
# src/pipelines/base.py
class BasePipeline(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...          # z.B. "nba_stats"

    @property
    def table_name(self) -> str:        # Standard: = name
        return self.name

    @abstractmethod
    def extract(self) -> pl.DataFrame: ...

    @abstractmethod
    def transform(self, df: pl.DataFrame) -> pl.DataFrame: ...

    def validate(self, df: pl.DataFrame) -> DQResult:
        return default_validate(df)     # überschreibbar

    def create_table_sql(self) -> str:
        return ""                       # leer = automatische DDL-Inferenz
```

```python
# src/pipelines/__init__.py
REGISTRY = {
    "nba_stats": NbaStatsPipeline,
    # "weather": WeatherPipeline,  ← neue Pipeline: 1 Zeile
}

def get_pipeline(name: str) -> BasePipeline:
    if name not in REGISTRY:
        raise ValueError(f"Unbekannte Pipeline: '{name}'")
    return REGISTRY[name]()
```

```python
# src/runner.py — ändert sich NIE
pipeline_name = os.getenv("PIPELINE", "nba_stats")
pipeline = get_pipeline(pipeline_name)
raw = pipeline.extract()
transformed = pipeline.transform(raw)
result = pipeline.validate(transformed)
if not result.passed: sys.exit(1)
load(transformed, pipeline.table_name, pipeline.create_table_sql())
```

### Neue Pipeline hinzufügen (2 Schritte)

```python
# 1. src/pipelines/weather.py
class WeatherPipeline(BasePipeline):
    @property
    def name(self): return "weather"

    def extract(self):
        # open-meteo.com — kostenlos, kein API-Key
        import urllib.request, json
        url = "https://api.open-meteo.com/v1/forecast?latitude=48.14&longitude=11.58&daily=temperature_2m_max"
        with urllib.request.urlopen(url) as r:
            data = json.load(r)
        return pl.DataFrame({"date": data["daily"]["time"],
                             "temp_max": data["daily"]["temperature_2m_max"]})

    def transform(self, df):
        return df.with_columns([
            pl.col("temp_max").mean().alias("avg_temp"),
            pl.col("date").str.to_date().alias("date"),
        ])

# 2. src/pipelines/__init__.py
REGISTRY = {
    "nba_stats": NbaStatsPipeline,
    "weather": WeatherPipeline,
}
```

**Deployment-Wechsel ohne Code-Änderung:**
```yaml
# ops-repository/helm/etl-stack/values.yaml
etl:
  pipeline: weather  # ← git commit → ArgoCD → K8s Job mit PIPELINE=weather
```

---

## DQ-Checks (validate.py)

### Generische Checks (für alle Pipelines)

```python
@dataclass
class DQResult:
    passed: bool
    failures: list[str]

def validate(df: pl.DataFrame) -> DQResult:
    failures = []
    if len(df) < 100:
        failures.append(f"Too few rows: {len(df)}")
    if df["player_id"].n_unique() != len(df):
        failures.append("Duplicate player_ids")
    for col in ["player_id", "player", "team", "pts", "efficiency_score"]:
        if df[col].null_count() > 0:
            failures.append(f"Nulls in '{col}'")
    if df.filter(pl.col("pts") < 0).height > 0:
        failures.append("Negative pts values")
    for pct in ["fg_pct", "fg3_pct", "ft_pct"]:
        if df.filter((pl.col(pct) < 0) | (pl.col(pct) > 1)).height > 0:
            failures.append(f"Out-of-range '{pct}'")
    return DQResult(passed=len(failures) == 0, failures=failures)
```

**Fail-Fast-Prinzip:** Wenn `validate()` fehlschlägt → `sys.exit(1)` → keine Daten in DB.
Lieber Pipeline-Fehler als falsche Daten in der Datenbank.

---

## Tests (pytest)

### Struktur
```
etl-repository/
├── pyproject.toml         → [tool.pytest.ini_options] pythonpath = ["src"]
└── tests/
    └── test_transform.py  → 16 Tests in 3 Klassen
```

### Klassen
```
TestNbaPipelineTransform  (6 Tests)
  - Spalten lowercase nach transform
  - efficiency_score wird berechnet
  - Sortierung descending
  - Jokić schlägt LeBron
  - Nur erwartete Spalten
  - Effizienz-Formel korrekt

TestValidate  (7 Tests)
  - Valid DataFrame besteht alle Checks
  - Zu wenige Rows → Fehler
  - Duplicate IDs → Fehler
  - Negative Punkte → Fehler
  - Prozentwert > 1 → Fehler
  - DQResult str() bei Pass
  - DQResult str() bei Fail

TestRegistry  (3 Tests)
  - get_pipeline("nba_stats") funktioniert
  - get_pipeline("unknown") wirft ValueError
  - Pipeline hat korrektes Interface
```

---

## Bekannte Probleme und Lösungen

| Problem | Ursache | Lösung |
|---------|---------|--------|
| `ImportError: libpq.5.dylib not found` | psycopg2-binary auf macOS ARM | `psycopg[binary]` verwenden (psycopg3) |
| `ModuleNotFoundError: no module named 'etl'` | pytest findet src/ nicht | `pyproject.toml`: `pythonpath = ["src"]` |
| `Connection.executemany` nicht gefunden | psycopg3 API anders als psycopg2 | `conn.cursor().executemany()` verwenden |
| kind cluster: kubeadm init schlägt fehl | Ressourcen-Konflikt mit minikube | minikube verwenden statt kind |
| ArgoCD Application "Unknown" Status | Image auf ghcr.io privat | Package auf ghcr.io öffentlich setzen |
| GitHub Actions Loop durch ci-commit | [skip ci] vergessen | Commit-Message mit `[skip ci]` endet |
| `polars.write_database` braucht pandas | Polars SQLAlchemy-Backend | psycopg3 direkt mit `executemany` nutzen |

---

## Umgebungsvariablen (vollständige Liste)

| Variable | Wo | Beschreibung |
|----------|----|--------------|
| `POSTGRES_HOST` | .env / K8s Secret | DB-Host (lokal: `localhost`, K8s: `postgres`) |
| `POSTGRES_PORT` | .env / K8s Secret | Standard: `5432` |
| `POSTGRES_DB` | .env / K8s Secret | Datenbankname: `nba_dih` |
| `POSTGRES_USER` | .env / K8s Secret | DB-User: `etl_user` |
| `POSTGRES_PASSWORD` | .env / K8s Secret | DB-Passwort |
| `PIPELINE` | docker run -e / K8s Job env | Pipeline-Name: `nba_stats` |
| `GITHUB_TOKEN` | GitHub Actions (automatisch) | Für ghcr.io Push + Git-Commit |

---

## Roadmap

| Phase | Status | Was | Tools |
|-------|--------|-----|-------|
| 1 | ✅ | Lokales Setup: ETL + Postgres | Python, Polars, Docker Compose, .env |
| 2 | ✅ | Docker Build & Run | Docker, docker networking |
| 3 | ✅ | CI/CD | GitHub Actions, ghcr.io |
| 4 | ✅ | GitOps: Registry + Deployment + Scheduling-Vorbereitung | Harbor, Helm, ArgoCD, minikube |
| 4.5 | ✅ | Plugin-Architektur | BasePipeline, Registry, runner.py |
| 5 | 🔜 | Scheduling | Apache Airflow, KubernetesExecutor, DAGs |
| 6 | 🔜 | Secrets | HashiCorp Vault |
| 7 | 🔜 | Azure Migration | AKS, Azure Container Registry, Azure PostgreSQL |

---

## Phase 5 Vorschau: Airflow

### Was Airflow löst

```
Problem jetzt:    Pipeline läuft nur bei git push (Code-Änderung)
Lösung Airflow:   Pipeline läuft täglich 06:00 — unabhängig von Code
```

### Scheduling-Repository Struktur (wird in Phase 5 angelegt)

```
scheduling-repository/
├── dags/
│   └── nba_pipeline_dag.py    ← DAG: täglich 06:00, PIPELINE=nba_stats
└── Dockerfile                 ← Image das die DAGs enthält
```

### DAG-Konzept

```python
# dags/nba_pipeline_dag.py
from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.job import KubernetesJobOperator
from datetime import datetime

with DAG("nba_pipeline", schedule="0 6 * * *", start_date=datetime(2025,1,1)) as dag:
    KubernetesJobOperator(
        task_id="run_etl",
        image="ghcr.io/thanghoang-pexon/etl-by-claude/etl-nba:latest",
        env_vars={"PIPELINE": "nba_stats"},
        # Postgres-Credentials aus K8s Secret
    )
```

### Airflow Deployment via Helm

```bash
helm repo add apache-airflow https://airflow.apache.org
helm install airflow apache-airflow/airflow \
  --namespace airflow --create-namespace \
  --set executor=KubernetesExecutor \
  --set dags.gitSync.enabled=true \
  --set dags.gitSync.repo=https://github.com/thanghoang-pexon/etl-by-claude.git \
  --set dags.gitSync.branch=main \
  --set dags.gitSync.subPath=scheduling-repository/dags
```

**KubernetesExecutor:** Jeder DAG-Task erstellt einen eigenen K8s Pod.
Perfekt für ETL: isoliert, skalierbar, keine dauerhaften Worker-Prozesse.

**git-sync:** Airflow lädt DAGs direkt aus GitHub — kein manuelles Kopieren.
Neuer DAG = git push → Airflow erkennt ihn automatisch.

---

## GitHub Repository

**URL:** https://github.com/thanghoang-pexon/etl-by-claude

**Branch-Strategie:**
- `main` → Production (CI/CD läuft, Images werden gebaut)
- Feature-Branches → Tests laufen, kein Image-Build

**Commit-Konventionen:**
```
feat: neue Funktionalität
refactor: Umstrukturierung ohne Verhaltensänderung
docs: nur README/agents.md
ci: GitHub Actions / Workflow-Änderungen
fix: Bugfix
```

---

*Dieses Dokument wird mit jeder Phase aktualisiert.*
*Zuletzt aktualisiert: Phase 4.5 — Plugin-Architektur*
