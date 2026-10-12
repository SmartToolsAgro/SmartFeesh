"""Every sales and purchasing document in one list: the "Documents" page (P2-T11, D-102).

This app has no table of its own. Sales and purchasing each describe their documents (`document_rows` in
their selectors); this module merges them, newest first. Writes never pass here: the page runs each action
through the endpoint of the app that owns the document.
"""

from dataclasses import dataclass

from apps.core.documents import DocumentFilters, DocumentRow
from apps.core.models import Organization
from apps.purchasing import selectors as purchasing
from apps.sales import selectors as sales

# More than a busy month of a small distributor: past it, the page asks for a narrower period.
MAX_ROWS = 1000

# Order of the types on the same day: the chain of a sale, then the chain of a purchase.
_TYPE_ORDER = {kind: index for index, kind in enumerate(("DV", "BL", "FA", "AV", "BA", "BR", "FF"))}


@dataclass(frozen=True)
class DocumentList:
    rows: list[DocumentRow]
    # How many matched before the cut at `MAX_ROWS`.
    total: int

    @property
    def truncated(self) -> bool:
        return self.total > len(self.rows)


def document_list(
    organization: Organization, filters: DocumentFilters, *, may_write: bool, tone: str = ""
) -> DocumentList:
    """The documents matching `filters` (and `tone` when given), newest day first, at most `MAX_ROWS`."""
    rows = [
        *sales.document_rows(organization, filters, may_write=may_write),
        *purchasing.document_rows(organization, filters, may_write=may_write),
    ]
    if tone:
        rows = [row for row in rows if row.tone == tone]
    rows.sort(key=lambda row: (-row.date.toordinal(), _TYPE_ORDER[row.type], -row.id))
    return DocumentList(rows=rows[:MAX_ROWS], total=len(rows))
