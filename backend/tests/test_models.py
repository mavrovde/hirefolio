import pytest
from datetime import datetime
from sqlalchemy import select

from app.models.post import Post


@pytest.mark.asyncio
async def test_create_post(db_session):
    """Test creating a post."""
    post = Post(
        title="Test Post",
        slug="test-post",
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
    assert post.slug == "test-post"
    assert post.language == "en"
    assert post.published is True
    assert len(post.embedding) == 768


@pytest.mark.asyncio
async def test_post_timestamps(db_session):
    """Test that timestamps are set automatically."""
    post = Post(
        title="Test Post",
        slug="test-post",
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
        slug="test-post",
        content="Content 1",
        language="en",
    )
    
    post2 = Post(
        title="Test Post 2",
        slug="test-post",
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
        slug="test-post",
        content="Content EN",
        language="en",
    )
    
    post_de = Post(
        title="Test Post DE",
        slug="test-post",
        content="Content DE",
        language="de",
    )
    
    db_session.add(post_en)
    db_session.add(post_de)
    await db_session.commit()
    
    result = await db_session.execute(select(Post))
    posts = result.scalars().all()
    
    assert len(posts) == 2
