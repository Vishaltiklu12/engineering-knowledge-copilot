from app.services.pagination import PaginationService


def test_pagination_service_returns_expected_slice_and_metadata() -> None:
    result = PaginationService.paginate_items([1, 2, 3, 4, 5], page=2, page_size=2)

    assert result.items == [3, 4]
    assert result.page == 2
    assert result.page_size == 2
    assert result.total_items == 5
    assert result.total_pages == 3
