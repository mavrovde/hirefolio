"""Admin-editable runtime site settings (#271).

The first key is `availability` — the owner's job-search state, rendered on
the public hero next to the hire-me CTA. Env-driven identity (#65) cannot
change without a redeploy; this can. Each key's allowed values are validated
HERE, so the KV table stays feature-agnostic.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.site_setting import SiteSetting
from app.services.auth import get_current_admin_user

router = APIRouter(
    prefix="/admin/site-settings",
    tags=["admin-site-settings"],
    dependencies=[Depends(get_current_admin_user)],
)

# The public vocabulary. Rendered verbatim by the frontend's i18n keys, so a
# new state means a new translation in BOTH en.json and de.json — the test
# that reads those files will fail otherwise.
AVAILABILITY_STATES = ("open", "listening", "not_looking")
AVAILABILITY_DEFAULT = "listening"
AVAILABILITY_KEY = "availability"


class AvailabilityOut(BaseModel):
    value: str


class AvailabilityIn(BaseModel):
    value: str


async def read_availability(db: AsyncSession) -> str:
    """Shared with the public /config/site endpoint: one definition of
    'current availability', default included."""
    row = await db.get(SiteSetting, AVAILABILITY_KEY)
    return row.value if row else AVAILABILITY_DEFAULT


@router.get("/availability", response_model=AvailabilityOut)
async def get_availability(db: AsyncSession = Depends(get_db)) -> AvailabilityOut:
    return AvailabilityOut(value=await read_availability(db))


@router.put("/availability", response_model=AvailabilityOut)
async def set_availability(
    body: AvailabilityIn, db: AsyncSession = Depends(get_db)
) -> AvailabilityOut:
    if body.value not in AVAILABILITY_STATES:
        raise HTTPException(
            status_code=422,
            detail=f"availability must be one of {', '.join(AVAILABILITY_STATES)}",
        )
    row = await db.get(SiteSetting, AVAILABILITY_KEY)
    if row is None:
        db.add(SiteSetting(key=AVAILABILITY_KEY, value=body.value))
    else:
        row.value = body.value
    await db.commit()
    return AvailabilityOut(value=body.value)
