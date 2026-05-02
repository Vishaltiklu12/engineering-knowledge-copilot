from dataclasses import dataclass
from math import ceil
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class PaginationResult(Generic[T]):
    items: list[T]
    page: int
    page_size: int
    total_items: int
    total_pages: int


class PaginationService:
    @staticmethod
    def build_result(*, items: list[T], page: int, page_size: int, total_items: int) -> PaginationResult[T]:
        total_pages = ceil(total_items / page_size) if total_items else 0
        return PaginationResult(
            items=items,
            page=page,
            page_size=page_size,
            total_items=total_items,
            total_pages=total_pages,
        )

    @staticmethod
    def paginate_items(items: list[T], page: int, page_size: int) -> PaginationResult[T]:
        start = (page - 1) * page_size
        end = start + page_size
        return PaginationService.build_result(
            items=items[start:end],
            page=page,
            page_size=page_size,
            total_items=len(items),
        )
