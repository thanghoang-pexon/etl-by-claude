"""
NBA Stats ETL Pipeline — täglicher Run via Airflow KubernetesPodOperator.

Wie es funktioniert:
  - Airflow Scheduler startet täglich um 06:00 UTC
  - Er erstellt einen Kubernetes Pod aus unserem ETL-Image
  - Der Pod läuft runner.py mit PIPELINE=nba_stats
  - Nach Fertigstellung wird der Pod automatisch gelöscht
  - Logs sind in der Airflow UI sichtbar

Neue Pipeline hinzufügen:
  - Neue Task-Instanz mit anderem PIPELINE-Wert anlegen (siehe unten)
  - Kein ETL-Code muss verändert werden
"""
from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from kubernetes.client import models as k8s

# ── Gemeinsame Einstellungen für alle Tasks ───────────────────────────────────

default_args = {
    "owner": "data-engineering",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": False,
}

# Postgres-Zugangsdaten aus K8s Secret (liegt im airflow-Namespace)
# → wird beim Cluster-Setup mit scripts/setup-airflow.sh angelegt
POSTGRES_ENV = [
    k8s.V1EnvVar(name="POSTGRES_HOST",  value="postgres.etl.svc.cluster.local"),
    k8s.V1EnvVar(name="POSTGRES_PORT",  value="5432"),
    k8s.V1EnvVar(
        name="POSTGRES_DB",
        value_from=k8s.V1EnvVarSource(
            secret_key_ref=k8s.V1SecretKeySelector(name="etl-postgres-credentials", key="POSTGRES_DB")
        ),
    ),
    k8s.V1EnvVar(
        name="POSTGRES_USER",
        value_from=k8s.V1EnvVarSource(
            secret_key_ref=k8s.V1SecretKeySelector(name="etl-postgres-credentials", key="POSTGRES_USER")
        ),
    ),
    k8s.V1EnvVar(
        name="POSTGRES_PASSWORD",
        value_from=k8s.V1EnvVarSource(
            secret_key_ref=k8s.V1SecretKeySelector(name="etl-postgres-credentials", key="POSTGRES_PASSWORD")
        ),
    ),
]

ETL_IMAGE = "ghcr.io/thanghoang-pexon/etl-by-claude/etl-nba:latest"

# ── DAG Definition ────────────────────────────────────────────────────────────

with DAG(
    dag_id="nba_stats_pipeline",
    description="Täglich NBA Spielerstatistiken laden (Extract → Transform → Validate → Load)",
    schedule="0 6 * * *",      # täglich 06:00 UTC
    start_date=datetime(2025, 1, 1),
    catchup=False,              # keine historischen Runs nachholen
    default_args=default_args,
    tags=["etl", "nba", "daily"],
) as dag:

    # ── Task 1: NBA Stats ETL ─────────────────────────────────────────────────
    run_nba_etl = KubernetesPodOperator(
        task_id="run_nba_etl",
        name="nba-etl-{{ ds_nodash }}",   # eindeutiger Pod-Name pro Execution Date
        namespace="airflow",
        image=ETL_IMAGE,
        image_pull_policy="Always",
        env_vars=[
            k8s.V1EnvVar(name="PIPELINE", value="nba_stats"),
            *POSTGRES_ENV,
        ],
        get_logs=True,
        is_delete_operator_pod=True,      # Pod nach Fertigstellung löschen
        on_finish_action="delete_pod",
        startup_timeout_seconds=120,
        container_resources=k8s.V1ResourceRequirements(
            requests={"memory": "256Mi", "cpu": "100m"},
            limits={"memory": "512Mi", "cpu": "500m"},
        ),
    )

    # ── Hier weitere Tasks hinzufügen ────────────────────────────────────────
    #
    # Beispiel: zweite Pipeline parallel ausführen
    # run_weather_etl = KubernetesPodOperator(
    #     task_id="run_weather_etl",
    #     name="weather-etl-{{ ds_nodash }}",
    #     namespace="airflow",
    #     image=ETL_IMAGE,
    #     env_vars=[k8s.V1EnvVar(name="PIPELINE", value="weather"), *POSTGRES_ENV],
    #     ...
    # )
    #
    # Abhängigkeit definieren (erst NBA, dann Weather):
    # run_nba_etl >> run_weather_etl
    #
    # Oder parallel (kein >>):
    # [run_nba_etl, run_weather_etl]
