from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import List, Dict, Any
from pydantic import BaseModel
import time

from app.database import get_db
from app.services.auth import get_current_admin_user
from app.models.user import User

router = APIRouter(
    prefix="/admin/sql", tags=["admin"], dependencies=[Depends(get_current_admin_user)]
)


class SqlQuery(BaseModel):
    query: str


@router.post("/execute", response_model=List[Dict[str, Any]])
async def execute_sql(
    sql: SqlQuery,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    start_time = time.time()
    try:
        # Check for forbidden keywords (very basic check, but test expects 400 on invalid query)

        import logging
        logging.warning("SQL execution via API is disabled for security reasons.")
        raise HTTPException(status_code=501, detail="SQL execution via API is disabled for security reasons.")

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


def _get_db_url():
    """Get the database URL with +asyncpg stripped for CLI tools."""
    from app.config import settings

    db_url = str(settings.database_url)
    if "+asyncpg" in db_url:
        db_url = db_url.replace("+asyncpg", "")
    return db_url


@router.get("/backup")
async def backup_database(current_user: User = Depends(get_current_admin_user)):
    import asyncio
    import os
    from datetime import datetime
    from fastapi.responses import StreamingResponse

    db_url = _get_db_url()

    # Generate backup filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"backup_mavrov_{timestamp}.sql"

    cmd = ["pg_dump", db_url]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ},
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=500, detail="pg_dump not found. Is postgresql-client installed?"
        )

    async def iter_backup():
        try:
            while True:
                chunk = await proc.stdout.read(8192)
                if not chunk:
                    break
                yield chunk

            await proc.wait()
            if proc.returncode != 0:
                stderr = await proc.stderr.read()
                print(f"Backup failed (exit {proc.returncode}): {stderr.decode()}")
        except Exception as e:
            print(f"Backup streaming error: {e}")
        finally:
            if proc.returncode is None:
                proc.terminate()

    return StreamingResponse(
        iter_backup(),
        media_type="application/sql",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/restore")
async def restore_database(
    file: UploadFile = File(...), current_user: User = Depends(get_current_admin_user)
):
    import asyncio
    import os

    if not file.filename or not file.filename.endswith(".sql"):
        raise HTTPException(status_code=400, detail="Only .sql files are allowed")

    db_url = _get_db_url()
    cmd = ["psql", db_url]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ},
        )

        # Read uploaded file content
        content = await file.read()
        file_size = len(content)

        # Communicate with timeout (5 minutes max for large dumps)
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=content), timeout=300
            )
        except asyncio.TimeoutError:
            proc.kill()
            raise HTTPException(
                status_code=500,
                detail=f"Restore timed out after 300s. File size: {file_size} bytes",
            )

        stdout_text = stdout.decode() if stdout else ""
        stderr_text = stderr.decode() if stderr else ""

        # Build detailed log
        log_lines = []
        log_lines.append(f"File: {file.filename} ({file_size:,} bytes)")
        log_lines.append(f"Exit code: {proc.returncode}")
        if stdout_text:
            # Truncate very long output
            if len(stdout_text) > 2000:
                stdout_text = (
                    stdout_text[:2000]
                    + f"\n... ({len(stdout_text)} chars total, truncated)"
                )
            log_lines.append(f"stdout:\n{stdout_text}")
        if stderr_text:
            if len(stderr_text) > 2000:
                stderr_text = (
                    stderr_text[:2000]
                    + f"\n... ({len(stderr_text)} chars total, truncated)"
                )
            log_lines.append(f"stderr:\n{stderr_text}")

        log_output = "\n".join(log_lines)

        if proc.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"Restore failed (exit {proc.returncode}):\n{log_output}",
            )

        return {"message": "Database restored successfully", "output": log_output}

    except FileNotFoundError:
        raise HTTPException(
            status_code=500, detail="psql not found. Is postgresql-client installed?"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Restore error: {str(e)}")
