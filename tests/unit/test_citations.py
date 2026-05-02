import uuid

from app.services.citations import CitationService
from app.services.retrieval import RetrievedChunk


def test_citation_service_maps_retrieved_chunks_to_source_documents() -> None:
    document_id = uuid.uuid4()
    chunk_id = uuid.uuid4()

    citations = CitationService().build(
        [
            RetrievedChunk(
                document_id=document_id,
                document_name="architecture.md",
                chunk_id=chunk_id,
                chunk_index=4,
                content="Asynchronous ingestion keeps upload latency low for users.",
                page_number=2,
                section_title="Ingestion",
                metadata={"chunking_strategy": "sliding_window"},
                score=0.93,
            )
        ]
    )

    assert len(citations) == 1
    assert citations[0].citation_id == 1
    assert citations[0].document_id == document_id
    assert citations[0].document_name == "architecture.md"
    assert citations[0].chunk_id == chunk_id
    assert citations[0].page == 2
    assert citations[0].score == 0.93
