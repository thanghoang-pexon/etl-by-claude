from abc import ABC, abstractmethod
import polars as pl
from validate import validate as default_validate, DQResult


class BasePipeline(ABC):
    """
    Jede Datenquelle erbt von dieser Klasse.
    Nur extract() und transform() müssen implementiert werden.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Eindeutiger Bezeichner — wird als PIPELINE env var und Tabellenname verwendet."""
        ...

    @property
    def table_name(self) -> str:
        """Name der Zieltabelle in PostgreSQL. Standard: gleich wie name."""
        return self.name

    @abstractmethod
    def extract(self) -> pl.DataFrame:
        """Daten aus der Quelle holen."""
        ...

    @abstractmethod
    def transform(self, df: pl.DataFrame) -> pl.DataFrame:
        """Transformationen + Berechnungen. Gibt das fertige DataFrame zurück."""
        ...

    def validate(self, df: pl.DataFrame) -> DQResult:
        """
        DQ-Checks. Standard: generische Checks aus validate.py.
        Kann pro Pipeline überschrieben werden für spezifische Regeln.
        """
        return default_validate(df)

    def create_table_sql(self) -> str:
        """
        DDL für die Zieltabelle. Wird automatisch aus dem DataFrame-Schema
        generiert wenn nicht überschrieben.
        Kann überschrieben werden für spezifische Constraints oder Indizes.
        """
        return ""  # db.py generiert DDL automatisch wenn leer
