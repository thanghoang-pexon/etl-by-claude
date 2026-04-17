"""
Universeller ETL-Runner.

Welche Pipeline läuft, wird durch die Umgebungsvariable PIPELINE gesteuert:
  PIPELINE=nba_stats  python runner.py
  PIPELINE=weather    python runner.py   ← morgen, übermorgen, ...

Neue Pipeline hinzufügen:
  1. Datei in src/pipelines/<name>.py anlegen (erbt von BasePipeline)
  2. In src/pipelines/__init__.py ins REGISTRY eintragen
  3. Fertig — kein anderer Code ändert sich
"""
import os
import sys
from dotenv import load_dotenv
from pipelines import get_pipeline
from db import load

load_dotenv()


def main() -> None:
    pipeline_name = os.getenv("PIPELINE", "nba_stats")
    print(f"[RUNNER] Starting pipeline: '{pipeline_name}'")

    pipeline = get_pipeline(pipeline_name)

    raw = pipeline.extract()
    transformed = pipeline.transform(raw)

    result = pipeline.validate(transformed)
    print(result)
    if not result.passed:
        sys.exit(1)

    load(transformed, pipeline.table_name, pipeline.create_table_sql())
    print(f"[RUNNER] Pipeline '{pipeline_name}' completed successfully.")


if __name__ == "__main__":
    main()
