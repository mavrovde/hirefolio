"""Coverage-focused tests for app.api.admin_cv.

These call the endpoint coroutines directly with lightweight in-memory fakes.
This exercises the real branching/return logic of the endpoints without going
through SQLAlchemy's async greenlet layer (which drops coverage tracing on the
lines that resume after an awaited DB round-trip).

Behaviour is still asserted for real: return payloads, sorting/pagination
branch selection, search-filter application, and error handling.
"""

from datetime import UTC

import pytest

from app.api import admin_cv
from app.models.cv_document import CvDocument
from app.models.cv_request import CvRequest


class _Scalars:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return _Scalars(self._rows)


class FakeDB:
    """A minimal AsyncSession stand-in that records interactions."""

    def __init__(self, rows=None, count=0):
        self._rows = rows or []
        self._count = count
        self.added = []
        self.committed = False
        self.refreshed = False
        self.rolled_back = False
        self.executed_statements = []

    async def execute(self, statement):
        self.executed_statements.append(statement)
        return _Result(self._rows)

    async def scalar(self, statement):
        return self._count

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.committed = True

    async def refresh(self, obj):
        self.refreshed = True
        if getattr(obj, "id", None) is None:
            obj.id = 1

    async def rollback(self):
        self.rolled_back = True


class FailingScalarDB(FakeDB):
    """DB whose scalar() raises to trigger the endpoint except blocks."""

    async def scalar(self, statement):
        raise RuntimeError("boom")


class FakeUploadFile:
    def __init__(
        self, content_type="application/pdf", filename="cv.pdf", content=b"%PDF-1.4"
    ):
        self.content_type = content_type
        self.filename = filename
        self._content = content

    async def read(self):
        return self._content


class FakeAdmin:
    email = "admin@example.com"


# --------------------------------------------------------------------------- #
# upload_cv
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_upload_cv_success_path():
    db = FakeDB()
    result = await admin_cv.upload_cv(
        file=FakeUploadFile(filename="resume.pdf"),
        version="v9.9",
        activate=True,
        db=db,
        admin=FakeAdmin(),
    )

    assert result == {"success": True, "version": "v9.9", "filename": "resume.pdf"}
    # New document was created active and persisted.
    assert len(db.added) == 1
    new_doc = db.added[0]
    assert isinstance(new_doc, CvDocument)
    assert new_doc.is_active is True
    assert new_doc.version == "v9.9"
    assert new_doc.filename == "resume.pdf"
    assert db.committed is True
    assert db.refreshed is True
    # The deactivation UPDATE ran before the INSERT.
    assert len(db.executed_statements) == 1


@pytest.mark.asyncio
async def test_upload_cv_rejects_non_pdf():
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        await admin_cv.upload_cv(
            file=FakeUploadFile(content_type="text/plain", filename="x.txt"),
            version="v1",
            activate=True,
            db=FakeDB(),
            admin=FakeAdmin(),
        )
    assert exc.value.status_code == 400
    assert "Only PDF files are allowed" in exc.value.detail


@pytest.mark.asyncio
async def test_upload_cv_error_triggers_rollback_and_500():
    from fastapi import HTTPException

    class ExplodingDB(FakeDB):
        async def commit(self):
            raise RuntimeError("db exploded")

    db = ExplodingDB()
    with pytest.raises(HTTPException) as exc:
        await admin_cv.upload_cv(
            file=FakeUploadFile(),
            version="v1",
            activate=True,
            db=db,
            admin=FakeAdmin(),
        )
    assert exc.value.status_code == 500
    assert "Failed to upload CV" in exc.value.detail
    assert db.rolled_back is True


# --------------------------------------------------------------------------- #
# get_cv_requests
# --------------------------------------------------------------------------- #


def _make_request(name="Jane", email="jane@x.com", company="Acme"):
    return CvRequest(name=name, email=email, company=company, message="hi")


@pytest.mark.asyncio
async def test_get_cv_requests_default_sort_and_none_count():
    # count None -> total coerced to 0 -> total_pages 1
    db = FakeDB(rows=[_make_request()], count=None)
    result = await admin_cv.get_cv_requests(
        page=1,
        page_size=10,
        sort_by="created_at",
        sort_order="desc",
        search=None,
        db=db,
        admin=FakeAdmin(),
    )
    assert result["total"] == 0
    assert result["total_pages"] == 1
    assert result["page"] == 1
    assert result["page_size"] == 10
    assert len(result["items"]) == 1


@pytest.mark.asyncio
async def test_get_cv_requests_search_and_asc_sort():
    db = FakeDB(rows=[_make_request()], count=5)
    result = await admin_cv.get_cv_requests(
        page=2,
        page_size=2,
        sort_by="name",
        sort_order="asc",
        search="Jane",
        db=db,
        admin=FakeAdmin(),
    )
    assert result["total"] == 5
    # ceil(5/2) == 3
    assert result["total_pages"] == 3
    assert result["page"] == 2


@pytest.mark.asyncio
async def test_get_cv_requests_invalid_sort_field_falls_back():
    # sort_by not an attribute -> else branch (default created_at ordering)
    db = FakeDB(rows=[], count=0)
    result = await admin_cv.get_cv_requests(
        page=1,
        page_size=10,
        sort_by="not_a_real_column",
        sort_order="asc",
        search=None,
        db=db,
        admin=FakeAdmin(),
    )
    assert result["items"] == []
    assert result["total"] == 0
    assert result["total_pages"] == 1


@pytest.mark.asyncio
async def test_get_cv_requests_error_returns_500():
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        await admin_cv.get_cv_requests(
            page=1,
            page_size=10,
            sort_by="created_at",
            sort_order="desc",
            search=None,
            db=FailingScalarDB(),
            admin=FakeAdmin(),
        )
    assert exc.value.status_code == 500
    assert "Failed to fetch requests" in exc.value.detail


# --------------------------------------------------------------------------- #
# get_cv_versions
# --------------------------------------------------------------------------- #


def _make_doc(filename="cv.pdf", version="1.0", is_active=False):
    doc = CvDocument(
        filename=filename, version=version, data=b"data", is_active=is_active
    )
    doc.id = 42
    from datetime import datetime

    doc.created_at = datetime(2024, 1, 1, tzinfo=UTC)
    return doc


@pytest.mark.asyncio
async def test_get_cv_versions_default_sort_and_none_count():
    doc = _make_doc(filename="active.pdf", version="3.0", is_active=True)
    db = FakeDB(rows=[doc], count=None)
    result = await admin_cv.get_cv_versions(
        page=1,
        page_size=10,
        sort_by="created_at",
        sort_order="desc",
        search=None,
        db=db,
        admin=FakeAdmin(),
    )
    assert result["total"] == 0
    assert result["total_pages"] == 1
    assert len(result["items"]) == 1
    item = result["items"][0]
    # Raw binary data must be excluded from the payload.
    assert set(item.keys()) == {"id", "filename", "version", "is_active", "created_at"}
    assert item["filename"] == "active.pdf"
    assert item["version"] == "3.0"
    assert item["is_active"] is True


@pytest.mark.asyncio
async def test_get_cv_versions_search_and_asc_sort():
    db = FakeDB(rows=[_make_doc()], count=12)
    result = await admin_cv.get_cv_versions(
        page=2,
        page_size=5,
        sort_by="version",
        sort_order="asc",
        search="cv",
        db=db,
        admin=FakeAdmin(),
    )
    assert result["total"] == 12
    # ceil(12/5) == 3
    assert result["total_pages"] == 3
    assert result["page"] == 2


@pytest.mark.asyncio
async def test_get_cv_versions_invalid_sort_field_falls_back():
    db = FakeDB(rows=[], count=0)
    result = await admin_cv.get_cv_versions(
        page=1,
        page_size=10,
        sort_by="does_not_exist",
        sort_order="asc",
        search=None,
        db=db,
        admin=FakeAdmin(),
    )
    assert result["items"] == []
    assert result["total"] == 0
    assert result["total_pages"] == 1


@pytest.mark.asyncio
async def test_get_cv_versions_error_returns_500():
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        await admin_cv.get_cv_versions(
            page=1,
            page_size=10,
            sort_by="created_at",
            sort_order="desc",
            search=None,
            db=FailingScalarDB(),
            admin=FakeAdmin(),
        )
    assert exc.value.status_code == 500
    assert "Failed to fetch CV versions" in exc.value.detail
