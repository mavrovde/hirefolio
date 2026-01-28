from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.database import get_db
from app.services.auth import get_current_admin_user
from app.models.cv_document import CvDocument
from app.models.cv_request import CvRequest
from app.models.user import User
from app.logger import logger

router = APIRouter(prefix="/api/admin/cv", tags=["Admin CV"])


@router.post("/upload")
async def upload_cv(
    file: UploadFile = File(...),
    version: str = Form(...),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    try:
        content = await file.read()

        # Deactivate all existing active documents
        await db.execute(update(CvDocument).values(is_active=False))

        # Create new document
        new_cv = CvDocument(
            filename=file.filename, data=content, version=version, is_active=True
        )
        db.add(new_cv)
        await db.commit()
        await db.refresh(new_cv)

        logger.info(f"Admin {admin.email} uploaded new CV version {version}")
        return {"success": True, "version": version, "filename": file.filename}

    except Exception as e:
        logger.error(f"Error uploading CV: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to upload CV")


@router.get("/requests")
async def get_cv_requests(
    db: AsyncSession = Depends(get_db), admin: User = Depends(get_current_admin_user)
):
    try:
        result = await db.execute(
            select(CvRequest).order_by(CvRequest.created_at.desc())
        )
        requests = result.scalars().all()
        return requests
    except Exception as e:
        logger.error(f"Error fetching CV requests: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch requests")


@router.get("/versions")
async def get_cv_versions(
    db: AsyncSession = Depends(get_db), admin: User = Depends(get_current_admin_user)
):
    try:
        result = await db.execute(
            select(CvDocument).order_by(CvDocument.created_at.desc())
        )
        # Exclude raw data to keep payload light
        documents = result.scalars().all()
        return [
            {
                "id": doc.id,
                "filename": doc.filename,
                "version": doc.version,
                "is_active": doc.is_active,
                "created_at": doc.created_at,
            }
            for doc in documents
        ]
    except Exception as e:
        logger.error(f"Error fetching CV versions: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch CV versions")
