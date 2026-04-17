# DAG-Image: enthält nur die DAG-Definitionen
# Wird genutzt wenn DAGs als Image (statt git-sync) verteilt werden
# Für unser Setup nutzen wir git-sync — dieses Dockerfile ist als Referenz

FROM apache/airflow:2.10.0
COPY dags/ /opt/airflow/dags/
