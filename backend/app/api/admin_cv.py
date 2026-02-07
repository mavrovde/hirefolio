from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from math import ceil
from typing import List, Any
from pydantic import BaseModel
from app.database import get_db
from app.services.auth import get_current_admin_user
from app.models.cv_document import CvDocument
from app.models.cv_request import CvRequest
from app.models.user import User
from app.logger import logger

router = APIRouter(prefix="/api/admin/cv", tags=["Admin CV"])


class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    page_size: int
    total_pages: int


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
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("created_at", description="Field to sort by"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="Sort order"),
    search: str = Query(None, description="Search in name, email, company"),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    try:
        # Build base query
        query = select(CvRequest)

        # Apply search filter
        if search:
            search_term = f"%{search}%"
            query = query.where(
                (CvRequest.name.ilike(search_term))
                | (CvRequest.email.ilike(search_term))
                | (CvRequest.company.ilike(search_term))
            )

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_raw = await db.scalar(count_query)
        total = int(total_raw) if total_raw is not None else 0

        # Apply sorting
        if hasattr(CvRequest, sort_by):
            order_column = getattr(CvRequest, sort_by)
            if sort_order == "desc":
                query = query.order_by(order_column.desc())
            else:
                query = query.order_by(order_column.asc())
        else:
            query = query.order_by(CvRequest.created_at.desc())

        # Apply pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        # Execute query
        result = await db.execute(query)
        requests = result.scalars().all()

        # Calculate total pages
        total_pages = ceil(total / page_size) if total > 0 else 1

        return {
            "items": requests,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }
    except Exception as e:
        logger.error(f"Error fetching CV requests: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch requests")


@router.get("/versions")
async def get_cv_versions(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("created_at", description="Field to sort by"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="Sort order"),
    search: str = Query(None, description="Search in version, filename"),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    try:
        # Build base query
        query = select(CvDocument)

        # Apply search filter
        if search:
            search_term = f"%{search}%"
            query = query.where(
                (CvDocument.version.ilike(search_term))
                | (CvDocument.filename.ilike(search_term))
            )

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_raw = await db.scalar(count_query)
        total = int(total_raw) if total_raw is not None else 0

        # Apply sorting
        if hasattr(CvDocument, sort_by):
            order_column = getattr(CvDocument, sort_by)
            if sort_order == "desc":
                query = query.order_by(order_column.desc())
            else:
                query = query.order_by(order_column.asc())
        else:
            query = query.order_by(CvDocument.created_at.desc())

        # Apply pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        # Execute query
        result = await db.execute(query)
        documents = result.scalars().all()

        # Calculate total pages
        total_pages = ceil(total / page_size) if total > 0 else 1

        # Exclude raw data to keep payload light
        return {
            "items": [
                {
                    "id": doc.id,
                    "filename": doc.filename,
                    "version": doc.version,
                    "is_active": doc.is_active,
                    "created_at": doc.created_at,
                }
                for doc in documents
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }
    except Exception as e:
        logger.error(f"Error fetching CV versions: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch CV versions")
