from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import List, Dict, Any
from pydantic import BaseModel
import time
import re

from app.database import get_db
from app.services.auth import get_current_admin_user
from app.models.user import User
from app.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/admin/sql",
    tags=["admin"],
    dependencies=[Depends(get_current_admin_user)]
)

# Maximum rows returned to prevent data exfiltration via large dumps
MAX_ROWS = 500

# DDL / destructive statements that must never be executed through this endpoint
_BLOCKED_PATTERN = re.compile(
    r"\b(DROP|TRUNCATE|ALTER|CREATE|GRANT|REVOKE|EXECUTE|EXEC|COPY|pg_read_file|pg_ls_dir)\b",
    re.IGNORECASE,
)


class SqlQuery(BaseModel):
    query: str


@router.post("/execute", response_model=List[Dict[str, Any]])
async def execute_sql(
    sql: SqlQuery,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")

    query = sql.query.strip()

    # ── Security: block dangerous DDL / system commands ─────────────────────
    if _BLOCKED_PATTERN.search(query):
        logger.warning(
            f"Admin SQL blocked dangerous keyword for user={current_user.username}: {query[:120]}"
        )
        raise HTTPException(
            status_code=400,
            detail="SQL Execution Error: query contains forbidden keywords (DROP, TRUNCATE, ALTER, CREATE, GRANT, REVOKE, EXECUTE, COPY)",
        )

    # ── Audit log ────────────────────────────────────────────────────────────
    logger.info(f"Admin SQL executed by user={current_user.username}: {query[:200]}")

    start_time = time.time()
    try:
        result = await db.execute(text(query))

        if query.upper().startswith("SELECT"):
            rows = result.mappings().all()
            # Enforce row cap
            if len(rows) > MAX_ROWS:
                raise HTTPException(
                    status_code=400,
                    detail=f"SQL Execution Error: result exceeds {MAX_ROWS} rows — add a LIMIT clause",
                )
            return [dict(row) for row in rows]
        else:
            await db.commit()
            duration = (time.time() - start_time) * 1000
            return [{"message": "Query executed successfully", "duration_ms": duration}]

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"SQL Execution Error: {str(e)}")
