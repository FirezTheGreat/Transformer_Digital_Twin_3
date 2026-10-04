"""Base Source Adapter Interface and Common Protocol."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Iterator, List, Optional
import pandas as pd

from app.models.telemetry import CanonicalEvent, RawTelemetryFrame


class BaseSourceAdapter(ABC):
    """Abstract base class for all telemetry source adapters."""

    @property
    @abstractmethod
    def adapter_id(self) -> str:
        """Unique identifier for this adapter instance (e.g. 'tripura_csv_v1')."""
        ...

    @property
    @abstractmethod
    def source_system(self) -> str:
        """Source system identifier (e.g. 'tripura_csv', 'cpri_mock')."""
        ...

    @abstractmethod
    def transform_record(
        self,
        raw_record: Dict[str, Any],
        asset_id: str,
        source_uri: str,
        source_record_id: Optional[str] = None,
    ) -> CanonicalEvent:
        """Transforms a single raw source dictionary into a CanonicalEvent."""
        ...

    @abstractmethod
    def stream_events(
        self,
        source_input: Any,
        asset_id: str,
    ) -> Iterator[CanonicalEvent]:
        """Streams CanonicalEvents from the provided source input."""
        ...
