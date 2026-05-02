from typing import TYPE_CHECKING

from app.schemas.query import CitationData

if TYPE_CHECKING:
    from app.services.retrieval import RetrievedChunk


class CitationService:
    def build(self, hits: list["RetrievedChunk"]) -> list[CitationData]:
        citations: list[CitationData] = []
        for index, hit in enumerate(hits, start=1):
            snippet = hit.content[:240].strip()
            citations.append(
                CitationData(
                    citation_id=index,
                    document_id=hit.document_id,
                    document_name=hit.document_name,
                    chunk_id=hit.chunk_id,
                    snippet=snippet,
                    page=hit.page_number,
                    score=round(hit.score, 4),
                )
            )
        return citations
