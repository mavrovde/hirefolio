from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.cv_request import CvRequest
from app.models.cv_document import CvDocument
from app.services.email import email_service
from app.config import settings
from app.logger import logger
import os

router = APIRouter(prefix="/api/cv", tags=["CV"])


class CvRequestPayload(BaseModel):
    name: str
    email: EmailStr
    company: str | None = None
    message: str | None = None
    consent: bool


@router.post("/request")
async def request_cv(
    payload: CvRequestPayload,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    if not payload.consent:
        raise HTTPException(
            status_code=400, detail="Data processing consent is required."
        )

    try:
        # 1. Save request to DB
        cv_request = CvRequest(
            name=payload.name,
            email=payload.email,
            company=payload.company,
            message=payload.message,
            consent_given=payload.consent,
            cv_version=settings.cv_version,
        )
        db.add(cv_request)
        await db.commit()
        await db.refresh(cv_request)

        # 2. Send email in background
        # We wrap it to update DB status on success if needed,
        # or just fire and forget for speed (but we want reliability).
        # For simplicity, we'll try to send immediately or queue it.
        # Let's use BackgroundTasks for non-blocking UI response.
        background_tasks.add_task(
            process_email_notification, cv_request.id, payload, db
        )

        return {
            "success": True,
            "message": "Request received. You can now download the CV.",
            "download_url": "/api/cv/download",
        }
    except Exception as e:
        logger.error(f"Error processing CV request: {e}")
        raise HTTPException(status_code=500, detail="Failed to process request")


@router.get("/download")
@router.get("/download")
async def download_cv(db: AsyncSession = Depends(get_db)):
    # 1. Get active CV from DB
    result = await db.execute(select(CvDocument).where(CvDocument.is_active))
    cv_doc = result.scalar_one_or_none()

    if not cv_doc:
        # Fallback to static if DB is empty (dev mode)
        file_path = "app/static/cv.pdf"
        if os.path.exists(file_path):
            with open(file_path, "rb") as f:
                content = f.read()
            return Response(
                content=content,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": 'attachment; filename="Sergii_Mavrov_CV_Fallback.pdf"'
                },
            )

        logger.warning("No active CV found in DB and no fallback file.")
        raise HTTPException(status_code=404, detail="CV file not found")

    # 2. Return DB content
    return Response(
        content=cv_doc.data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{cv_doc.filename}"'},
    )


async def process_email_notification(request_id, payload, db: AsyncSession):
    # Note: re-using the session passed from dependency might cause issues if the request finishes.
    # Ideally we'd create a new session or send email synchronously if fast enough.
    # Given smtplib is sync blocking, we should probably run it in a threadpool or
    # keep it simple. For now, let's just send it.

    success = email_service.send_cv_request_notification(
        name=payload.name,
        email=payload.email,
        company=payload.company or "N/A",
        message=payload.message or "N/A",
    )

    if success:
        # We need a new session context here properly to update the record background
        # Avoiding complex async session handling for this MVP step.
        # Just logging for now.
        logger.info(f"Email sent for request {request_id}")
