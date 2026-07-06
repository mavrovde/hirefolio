import pytest
from datetime import datetime
from sqlalchemy import select

from app.models.post import Post


@pytest.mark.asyncio
async def test_create_post(db_session):
    """Test creating a post."""
    post = Post(
        title="Test Post",
        slug="test-post-create",
        content="Test content",
        summary="Test summary",
        language="en",
        published=True,
        embedding=[0.1] * 768,
    )

    db_session.add(post)
    await db_session.commit()
    await db_session.refresh(post)

    assert post.id is not None
    assert post.title == "Test Post"
    assert post.slug == "test-post-create"
    assert post.language == "en"
    assert post.published is True
    assert len(post.embedding) == 768


@pytest.mark.asyncio
async def test_post_timestamps(db_session):
    """Test that timestamps are set automatically."""
    post = Post(
        title="Test Post",
        slug="test-post-timestamps",
        content="Test content",
        language="en",
    )

    db_session.add(post)
    await db_session.commit()
    await db_session.refresh(post)

    assert isinstance(post.created_at, datetime)
    assert isinstance(post.updated_at, datetime)


@pytest.mark.asyncio
async def test_unique_slug_language_constraint(db_session):
    """Test that slug + language combination must be unique."""
    post1 = Post(
        title="Test Post 1",
        slug="test-post-unique",
        content="Content 1",
        language="en",
    )

    post2 = Post(
        title="Test Post 2",
        slug="test-post-unique",
        content="Content 2",
        language="en",
    )

    db_session.add(post1)
    await db_session.commit()

    db_session.add(post2)

    with pytest.raises(Exception):  # IntegrityError
        await db_session.commit()


@pytest.mark.asyncio
async def test_same_slug_different_language(db_session):
    """Test that same slug can exist for different languages."""
    post_en = Post(
        title="Test Post EN",
        slug="test-post-multi",
        content="Content EN",
        language="en",
    )

    post_de = Post(
        title="Test Post DE",
        slug="test-post-multi",
        content="Content DE",
        language="de",
    )

    db_session.add(post_en)
    db_session.add(post_de)
    await db_session.commit()

    result = await db_session.execute(select(Post))
    posts = result.scalars().all()

    assert len(posts) == 2


@pytest.mark.asyncio
async def test_post_provenance_columns_nullable(db_session):
    """New provenance columns default to None when not supplied."""
    post = Post(
        title="Provenance Test",
        slug="provenance-nullable",
        content="Content",
        language="en",
    )
    db_session.add(post)
    await db_session.commit()
    await db_session.refresh(post)

    assert post.source_urn is None
    assert post.source_url is None
    assert post.posted_at is None


@pytest.mark.asyncio
async def test_source_urn_unique_constraint(db_session):
    """Two posts with the same non-null source_urn must raise an integrity error."""
    post1 = Post(
        title="URN Post 1",
        slug="urn-post-1",
        content="Content 1",
        language="en",
        source_urn="urn:li:activity:111111111",
    )
    post2 = Post(
        title="URN Post 2",
        slug="urn-post-2",
        content="Content 2",
        language="en",
        source_urn="urn:li:activity:111111111",  # same URN — must be rejected
    )

    db_session.add(post1)
    await db_session.commit()

    db_session.add(post2)
    with pytest.raises(Exception):  # IntegrityError from unique partial index
        await db_session.commit()


@pytest.mark.asyncio
async def test_source_urn_null_not_unique(db_session):
    """Two posts with source_urn=None must both persist (NULLs are not unique)."""
    post1 = Post(
        title="No URN Post 1",
        slug="no-urn-1",
        content="Content 1",
        language="en",
        source_urn=None,
    )
    post2 = Post(
        title="No URN Post 2",
        slug="no-urn-2",
        content="Content 2",
        language="en",
        source_urn=None,
    )

    db_session.add(post1)
    db_session.add(post2)
    await db_session.commit()
    await db_session.refresh(post1)
    await db_session.refresh(post2)

    assert post1.source_urn is None
    assert post2.source_urn is None
