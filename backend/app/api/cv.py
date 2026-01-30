from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.cv_request import CvRequest
from app.models.cv_document import CvDocument
from app.services.email import email_service
from app.logger import logger

router = APIRouter(prefix="/api/cv", tags=["CV"])


class CvRequestPayload(BaseModel):
    name: str = Field(..., min_length=2)
    email: EmailStr
    company: str | None = None
    message: str = Field(..., min_length=5)


@router.post("/request")
async def request_cv(
    payload: CvRequestPayload,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    try:
        # Pre-check: Verify there is an active CV document
        # This prevents users from being "informed" they can download it when it's missing.
        result = await db.execute(select(CvDocument).where(CvDocument.is_active))
        active_cv = result.scalar_one_or_none()

        if not active_cv:
            logger.error("CV missing: No active DB entry found.")
            raise HTTPException(status_code=404, detail="CV_ERROR_UNAVAILABLE")

        # 1. Save request to DB
        cv_request = CvRequest(
            name=payload.name,
            email=payload.email,
            company=payload.company,
            message=payload.message,
            consent_given=True,  # Default to true as per new policy
            cv_version=active_cv.version,
        )
        db.add(cv_request)
        await db.commit()
        await db.refresh(cv_request)

        # 2. Send emails in background
        background_tasks.add_task(process_email_notifications, cv_request.id, payload)

        return {
            "success": True,
            "message": "Request received. You can now download the CV.",
            "download_url": "/api/cv/download",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing CV request: {e}")
        raise HTTPException(status_code=500, detail="Failed to process request")


@router.get("/download")
async def download_cv(db: AsyncSession = Depends(get_db)):
    # 1. Get active CV from DB
    result = await db.execute(select(CvDocument).where(CvDocument.is_active))
    cv_doc = result.scalar_one_or_none()

    if not cv_doc:
        logger.warning("No active CV found in DB.")
        raise HTTPException(status_code=404, detail="CV_ERROR_UNAVAILABLE")

    # 2. Return DB content
    return Response(
        content=cv_doc.data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{cv_doc.filename}"'},
    )


async def process_email_notifications(request_id, payload):
    # 1. Notify Admin
    email_service.send_cv_request_notification(
        name=payload.name,
        email=payload.email,
        company=payload.company or "N/A",
        message=payload.message,
    )

    # 2. Notify Requester
    email_service.send_requester_confirmation(name=payload.name, email=payload.email)

    logger.info(f"Emails sent for CV request {request_id}")
