from abc import ABC, abstractmethod
from typing import Any

from jobnotifier.models import Posting


class Source(ABC):
    """Common interface every tier's source adapter implements."""

    source_id: str
    tier: int

    @abstractmethod
    def fetch(self) -> Any:
        """Retrieve raw data from the source. Raises on failure."""

    @abstractmethod
    def parse(self, raw: Any) -> list[Posting]:
        """Convert raw fetched data into the common Posting shape."""
