from app.services.chunker import PagePayload, SlidingWindowChunkingStrategy


def test_sliding_window_chunking_preserves_overlap_and_metadata() -> None:
    strategy = SlidingWindowChunkingStrategy(chunk_size_words=5, chunk_overlap_words=2)

    chunks = strategy.chunk_document(
        [
            PagePayload(
                text="one two three four five six seven eight",
                page_number=3,
                metadata={"source": "design-doc"},
            )
        ]
    )

    assert [chunk.content for chunk in chunks] == [
        "one two three four five",
        "four five six seven eight",
    ]
    assert [chunk.chunk_index for chunk in chunks] == [0, 1]
    assert chunks[0].metadata["chunking_strategy"] == "sliding_window"
    assert chunks[0].metadata["start_word"] == 0
    assert chunks[1].metadata["start_word"] == 3
    assert chunks[1].metadata["source"] == "design-doc"
