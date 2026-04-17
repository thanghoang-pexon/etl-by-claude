from pipelines.nba_stats import NbaStatsPipeline
from pipelines.base import BasePipeline

# Neue Pipeline hinzufügen? Hier registrieren + Datei in pipelines/ anlegen.
REGISTRY: dict[str, type[BasePipeline]] = {
    "nba_stats": NbaStatsPipeline,
}


def get_pipeline(name: str) -> BasePipeline:
    if name not in REGISTRY:
        available = ", ".join(REGISTRY.keys())
        raise ValueError(f"Unbekannte Pipeline: '{name}'. Verfügbar: {available}")
    return REGISTRY[name]()
