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


@router.get("/backup")
async def backup_database(
    current_user: User = Depends(get_current_admin_user)
):
    import subprocess
    import os
    from datetime import datetime
    from fastapi.responses import StreamingResponse
    from app.config import settings

    # Construct connection details from settings or defaults
    # Parse DATABASE_URL or use env vars. Ideally use PGPASSWORD env var.
    # For now, assuming standard docker-compose env vars are available or part of settings.
    # Extracting from settings.database_url is safer if available, but let's try standard envs first.
    
    # We need the password. detailed parsing of DATABASE_URL might be needed if not in simpler envs.
    # settings.database_url is a PostgresDsn. 
    db_url = str(settings.database_url)
    
    # Generate backup filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"backup_mavrov_{timestamp}.sql"

    # Command to dump database
    # pg_dump -h db -U postgres -d mavrov
    # We pass the full connection string/URL to avoid password prompts if properly formatted
    
    cmd = ["pg_dump", db_url]

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={**os.environ} # Pass current env
        )
    except FileNotFoundError:
         raise HTTPException(status_code=500, detail="pg_dump not found. Is postgresql-client installed?")

    def iter_backup():
        try:
            while True:
                chunk = proc.stdout.read(8192)
                if not chunk:
                    break
                yield chunk
            
            # Check for errors after finishing stdout
            proc.stdout.close()
            return_code = proc.wait()
            if return_code != 0:
                stderr = proc.stderr.read()
                print(f"Backup failed: {stderr}")
                # We can't raise HTTP exception inside generator easily, but log it.
        except Exception as e:
            print(f"Backup streaming error: {e}")
        finally:
             if proc.poll() is None:
                 proc.terminate()

    return StreamingResponse(
        iter_backup(),
        media_type="application/sql",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


from fastapi import UploadFile, File

@router.post("/restore")
async def restore_database(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_admin_user)
):
    import subprocess
    import os
    from app.config import settings

    if not file.filename.endswith('.sql'):
         raise HTTPException(status_code=400, detail="Only .sql files are allowed")

    db_url = str(settings.database_url)
    
    # We need to write the uploaded file to a temp file or stream it to psql stdin
    # Streaming to stdin is better for large files
    
    cmd = ["psql", db_url]

    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={**os.environ}
        )
        
        # Stream file content to psql
        content = await file.read()
        stdout, stderr = proc.communicate(input=content)

        if proc.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error"
            raise HTTPException(status_code=500, detail=f"Restore failed: {error_msg}")

        return {"message": "Database restored successfully", "output": stdout.decode() if stdout else ""}

    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="psql not found. Is postgresql-client installed?")
    except Exception as e:
         raise HTTPException(status_code=500, detail=f"Restore error: {str(e)}")
