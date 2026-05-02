from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Sequence

from app.core.config import get_settings
from app.core.exceptions import ValidationAppError


@dataclass
class PagePayload:
    text: str
    page_number: int | None
    section_title: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChunkPayload:
    chunk_index: int
    content: str
    token_count: int
    page_number: int | None
    section_title: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ChunkingStrategy(ABC):
    name: str

    @abstractmethod
    def chunk_document(self, pages: Sequence[PagePayload]) -> list[ChunkPayload]:
        raise NotImplementedError


class SlidingWindowChunkingStrategy(ChunkingStrategy):
    name = "sliding_window"

    def __init__(self, chunk_size_words: int | None = None, chunk_overlap_words: int | None = None) -> None:
        settings = get_settings()
        self.chunk_size_words = chunk_size_words or settings.chunk_size_words
        self.chunk_overlap_words = chunk_overlap_words or settings.chunk_overlap_words

    def chunk_document(self, pages: Sequence[PagePayload]) -> list[ChunkPayload]:
        payloads: list[ChunkPayload] = []
        step = max(1, self.chunk_size_words - self.chunk_overlap_words)
        next_chunk_index = 0

        for page in pages:
            words = page.text.split()
            if not words:
                continue

            for start in range(0, len(words), step):
                window = words[start : start + self.chunk_size_words]
                if not window:
                    continue

                payloads.append(
                    ChunkPayload(
                        chunk_index=next_chunk_index,
                        content=" ".join(window).strip(),
                        token_count=len(window),
                        page_number=page.page_number,
                        section_title=page.section_title,
                        metadata={
                            **page.metadata,
                            "chunking_strategy": self.name,
                            "start_word": start,
                            "end_word": start + len(window),
                        },
                    )
                )
                next_chunk_index += 1

                if start + self.chunk_size_words >= len(words):
                    break

        return payloads


def get_chunking_strategy() -> ChunkingStrategy:
    settings = get_settings()

    if settings.chunking_strategy == "sliding_window":
        return SlidingWindowChunkingStrategy()

    raise ValidationAppError(
        "Unsupported chunking strategy configured.",
        details={"chunking_strategy": settings.chunking_strategy},
    )
