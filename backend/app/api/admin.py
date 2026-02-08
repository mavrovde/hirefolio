from typing import Any, List, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel

from app.database import get_db
from app.services.auth import get_current_user
from app.models.user import User

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    responses={404: {"description": "Not found"}},
)

class SqlQuery(BaseModel):
    query: str

@router.post("/sql/execute", response_model=List[Dict[str, Any]])
async def execute_sql(
    sql: SqlQuery,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Execute raw SQL query.
    Restricted to superusers.
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )

    try:
        # Execute the query
        result = await db.execute(text(sql.query))
        
        # Determine if it's a SELECT query that returns rows
        if result.returns_rows:
            # Fetch all rows and convert to list of dicts
            rows = result.fetchall()
            keys = result.keys()
            return [dict(zip(keys, row)) for row in rows]
        else:
            # For INSERT, UPDATE, DELETE, etc., commit the transaction
            await db.commit()
            return [{"status": "success", "rows_affected": result.rowcount}]

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"SQL Execution Error: {str(e)}",
        )
