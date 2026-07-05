"""Coverage-focused tests for app.api.cv.download_cv.

The endpoint functions are invoked directly (not through the ASGI transport) so
coverage reliably traces the handler body. These exercise the branches that the
existing suite leaves uncovered:
  - tracking block where req_id has no matching CvRequest (branch 82->92)
  - active-CV lookup miss -> 404 (lines 96-97) and its HTTPException re-raise (108)
  - the tracking-failure swallow path and the happy paths, for good measure.
"""

import uuid

import pytest
from fastapi import HTTPException

from app.api.cv import download_cv
from app.models.cv_document import CvDocument
from app.models.cv_request import CvRequest


async def _add_active_cv(db_session, data=b"pdf bytes", version="v9.9"):
    doc = CvDocument(
        id=uuid.uuid4(),
        filename="cov.pdf",
        data=data,
        version=version,
        is_active=True,
    )
    db_session.add(doc)
    await db_session.commit()
    return doc


@pytest.mark.asyncio
async def test_download_req_id_no_matching_request(db_session):
    """req_id given but no matching CvRequest -> false branch of `if cv_request` (82->92)."""
    await _add_active_cv(db_session, data=b"no match content")

    missing_id = str(uuid.uuid4())
    resp = await download_cv(req_id=missing_id, db=db_session)

    assert resp.status_code == 200
    assert resp.body == b"no match content"
    assert resp.media_type == "application/pdf"


@pytest.mark.asyncio
async def test_download_updates_tracking_for_existing_request(db_session):
    """req_id matches -> tracking fields updated (lines 82-87)."""
    await _add_active_cv(db_session, data=b"tracked content")

    req_id = uuid.uuid4()
    req = CvRequest(
        id=req_id,
        name="Cov Tracker",
        email="cov-track@example.com",
        message="Coverage tracking",
        cv_version="v9.9",
        consent_given=True,
    )
    db_session.add(req)
    await db_session.commit()

    resp = await download_cv(req_id=str(req_id), db=db_session)
    assert resp.status_code == 200
    assert resp.body == b"tracked content"

    from sqlalchemy import select

    result = await db_session.execute(select(CvRequest).where(CvRequest.id == req_id))
    updated = result.scalar_one()
    assert updated.download_count == 1
    assert updated.downloaded_at is not None


@pytest.mark.asyncio
async def test_download_tracking_failure_is_swallowed(db_session):
    """A malformed req_id makes the tracking query raise; inner except swallows it (88-89)."""
    await _add_active_cv(db_session, data=b"resilient content")

    # Not a valid UUID -> the CvRequest query raises a DB error inside the inner try.
    resp = await download_cv(req_id="not-a-valid-uuid", db=db_session)

    # Tracking failure must not break the download; the PDF is still served.
    assert resp.status_code == 200
    assert resp.body == b"resilient content"


@pytest.mark.asyncio
async def test_download_no_active_cv_raises_404(db_session):
    """No active CV -> 404 CV_ERROR_UNAVAILABLE (lines 95-97), re-raised via 107-108."""
    with pytest.raises(HTTPException) as exc_info:
        await download_cv(req_id=None, db=db_session)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "CV_ERROR_UNAVAILABLE"


@pytest.mark.asyncio
async def test_download_success_without_req_id(db_session):
    """Happy path with no req_id serves the active CV bytes and disposition header."""
    await _add_active_cv(db_session, data=b"plain content")

    resp = await download_cv(req_id=None, db=db_session)
    assert resp.status_code == 200
    assert resp.body == b"plain content"
    assert 'attachment; filename="cov.pdf"' in resp.headers["content-disposition"]
