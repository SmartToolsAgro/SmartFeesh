"""Pagination for lists that keep growing (batches, movements, invoices). Short lists are not paginated."""

from rest_framework.pagination import LimitOffsetPagination


class PagedList(LimitOffsetPagination):
    """`?limit=&offset=`: 50 rows by default, 200 at most. The answer carries `count`, `next`, `previous`
    and `results`."""

    default_limit = 50
    max_limit = 200
