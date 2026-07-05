"""Coverage-focused tests for app.api.tags.

These tests invoke the endpoint coroutines directly with a real async DB
session so that coverage.py traces the endpoint bodies (which are not traced
reliably when the same code runs behind the httpx ASGI transport). They assert
real behaviour: tag aggregation, search filtering, sorting, pagination, and the
rename/delete rowcount messages.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.tags import (
    PaginatedTagStats,
    TagRename,
    delete_tag,
    list_tags,
    rename_tag,
)
from app.models.post import Post


async def _add_post(db: AsyncSession, slug: str, tags: list[str]) -> None:
    db.add(Post(title=slug, slug=slug, content="content", tags=tags))
    await db.commit()


@pytest.mark.asyncio
async def test_list_tags_aggregates_counts(db_session: AsyncSession):
    """Rows returned by unnest are turned into TagStat with usage counts."""
    await _add_post(db_session, "cov-p1", ["python", "api"])
    await _add_post(db_session, "cov-p2", ["python", "web"])

    result = await list_tags(
        page=1,
        page_size=10,
        sort_by="count",
        sort_order="desc",
        search=None,
        db=db_session,
        current_user=None,
    )

    assert isinstance(result, PaginatedTagStats)
    counts = {t.name: t.count for t in result.items}
    assert counts["python"] == 2
    assert counts["api"] == 1
    assert counts["web"] == 1
    assert result.total == 3
    assert result.total_pages == 1


@pytest.mark.asyncio
async def test_list_tags_search_filter_case_insensitive(db_session: AsyncSession):
    """The search branch filters aggregated tags case-insensitively."""
    await _add_post(db_session, "cov-s1", ["Docker", "Python", "docker-compose"])

    result = await list_tags(
        page=1,
        page_size=10,
        sort_by="name",
        sort_order="asc",
        search="DOCKER",
        db=db_session,
        current_user=None,
    )

    names = [t.name for t in result.items]
    assert names == ["docker-compose", "Docker"] or names == ["Docker", "docker-compose"]
    assert result.total == 2
    assert "Python" not in names


@pytest.mark.asyncio
async def test_list_tags_sort_by_name(db_session: AsyncSession):
    """sort_by=name path orders tags by name with reverse per sort_order."""
    await _add_post(db_session, "cov-n1", ["zebra", "alpha", "beta"])

    asc = await list_tags(
        page=1,
        page_size=10,
        sort_by="name",
        sort_order="asc",
        search=None,
        db=db_session,
        current_user=None,
    )
    assert [t.name for t in asc.items] == ["alpha", "beta", "zebra"]

    desc = await list_tags(
        page=1,
        page_size=10,
        sort_by="name",
        sort_order="desc",
        search=None,
        db=db_session,
        current_user=None,
    )
    assert [t.name for t in desc.items] == ["zebra", "beta", "alpha"]


@pytest.mark.asyncio
async def test_list_tags_sort_by_count(db_session: AsyncSession):
    """Default sort_by path orders tags by count."""
    await _add_post(db_session, "cov-c1", ["common"])
    await _add_post(db_session, "cov-c2", ["common", "rare"])
    await _add_post(db_session, "cov-c3", ["common"])

    desc = await list_tags(
        page=1,
        page_size=10,
        sort_by="count",
        sort_order="desc",
        search=None,
        db=db_session,
        current_user=None,
    )
    assert desc.items[0].name == "common"
    assert desc.items[0].count == 3
    assert desc.items[-1].name == "rare"


@pytest.mark.asyncio
async def test_list_tags_pagination(db_session: AsyncSession):
    """Pagination slices the aggregated list and computes total_pages > 1."""
    await _add_post(db_session, "cov-pg1", ["t0", "t1", "t2", "t3", "t4"])
    await _add_post(db_session, "cov-pg2", ["t5", "t6", "t7", "t8", "t9"])
    await _add_post(db_session, "cov-pg3", ["t10", "t11", "t12", "t13", "t14"])

    page1 = await list_tags(
        page=1,
        page_size=10,
        sort_by="name",
        sort_order="asc",
        search=None,
        db=db_session,
        current_user=None,
    )
    assert page1.total == 15
    assert len(page1.items) == 10
    assert page1.total_pages == 2

    page2 = await list_tags(
        page=2,
        page_size=10,
        sort_by="name",
        sort_order="asc",
        search=None,
        db=db_session,
        current_user=None,
    )
    assert len(page2.items) == 5


@pytest.mark.asyncio
async def test_list_tags_empty_total_pages_one(db_session: AsyncSession):
    """With no tags, total is 0 and total_pages defaults to 1 (else branch)."""
    result = await list_tags(
        page=1,
        page_size=10,
        sort_by="count",
        sort_order="desc",
        search=None,
        db=db_session,
        current_user=None,
    )
    assert result.total == 0
    assert result.items == []
    assert result.total_pages == 1


@pytest.mark.asyncio
async def test_rename_tag_reports_affected_rows(db_session: AsyncSession):
    """rename_tag replaces the tag and reports affected row count."""
    await _add_post(db_session, "cov-r1", ["old-tag", "keep"])
    await _add_post(db_session, "cov-r2", ["old-tag"])

    res = await rename_tag(
        old_name="old-tag",
        tag_data=TagRename(new_name="new-tag"),
        db=db_session,
        current_user=None,
    )
    assert res == {"message": "Tag renamed. Affected 2 posts."}

    db_session.expire_all()
    refreshed = await db_session.get(Post, (await _get_id(db_session, "cov-r1")))
    assert "new-tag" in refreshed.tags
    assert "old-tag" not in refreshed.tags


@pytest.mark.asyncio
async def test_delete_tag_reports_affected_rows(db_session: AsyncSession):
    """delete_tag removes the tag and reports affected row count."""
    await _add_post(db_session, "cov-d1", ["to-delete", "keep"])

    res = await delete_tag(
        name="to-delete",
        db=db_session,
        current_user=None,
    )
    assert res == {"message": "Tag removed. Affected 1 posts."}

    db_session.expire_all()
    refreshed = await db_session.get(Post, (await _get_id(db_session, "cov-d1")))
    assert "to-delete" not in refreshed.tags
    assert "keep" in refreshed.tags


async def _get_id(db: AsyncSession, slug: str) -> int:
    from sqlalchemy import select

    row = await db.execute(select(Post.id).where(Post.slug == slug))
    return row.scalar_one()
