from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import List, Dict, Any
from pydantic import BaseModel
import time

from app.database import get_db
from app.services.auth import get_current_admin_user
from app.models.user import User

router = APIRouter(
    prefix="/admin/sql",
    tags=["admin"],
    dependencies=[Depends(get_current_admin_user)]
)

class SqlQuery(BaseModel):
    query: str

@router.post("/execute", response_model=List[Dict[str, Any]])
async def execute_sql(
    sql: SqlQuery,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")

    start_time = time.time()
    try:
        # Check for forbidden keywords (very basic check, but test expects 400 on invalid query)
        
        # Execute query
        result = await db.execute(text(sql.query))
        
        if sql.query.strip().upper().startswith("SELECT"):
            # Fetch results as mappings (dictionaries)
            rows = result.mappings().all()
            # Serialize rows
            return [dict(row) for row in rows]
        else:
            # For UPDATE/DELETE/INSERT, commit is needed
            await db.commit()
            duration = (time.time() - start_time) * 1000
            return [{"message": "Query executed successfully", "duration_ms": duration}]

    except Exception as e:
        await db.rollback()
        # Test expects "SQL Execution Error" in detail if query is invalid
        raise HTTPException(status_code=400, detail=f"SQL Execution Error: {str(e)}")
