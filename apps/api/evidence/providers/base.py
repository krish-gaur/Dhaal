"""Base protocol for extraction providers."""

from __future__ import annotations

from typing import Protocol

from evidence.extract import Clause


class ExtractionProvider(Protocol):
    def extract_clauses(
        self,
        page_texts: list[str],
        document_id: str,
    ) -> list[Clause]: ...

    @property
    def provider_name(self) -> str: ...
