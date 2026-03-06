from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from math import ceil
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, field_validator, ConfigDict, Field

from app.database import get_db
from app.models.post import Post
from app.services.embeddings import get_embedding
from app.services.auth import get_current_admin_user, get_current_user_optional
from app.models.user import User

router = APIRouter(prefix="/posts", tags=["posts"])


class PostCreate(BaseModel):
    title: str
    slug: str
    content: str
    summary: Optional[str] = None
    image_url: Optional[str] = None
    language: str = "en"
    published: bool = False
    tags: List[str] = []

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v):
        if len(v) > 5:
            raise ValueError("Max 5 tags allowed")
        return v


class PostUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    summary: Optional[str] = None
    image_url: Optional[str] = None
    language: Optional[str] = None
    published: Optional[bool] = None
    tags: Optional[List[str]] = None

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v):
        if v is not None and len(v) > 5:
            raise ValueError("Max 5 tags allowed")
        return v


class PostResponse(BaseModel):
    id: int
    title: str
    slug: str
    content: str
    summary: Optional[str]
    image_url: Optional[str] = Field(None, validation_alias="display_image_url")
    language: str
    published: bool
    tags: List[str]
    created_at: str
    updated_at: str

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class PostListResponse(BaseModel):
    id: int
    title: str
    slug: str
    summary: Optional[str]
    image_url: Optional[str] = Field(None, validation_alias="display_image_url")
    language: str
    published: bool
    tags: List[str]
    created_at: str

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class PaginatedPostListResponse(BaseModel):
    items: List[PostListResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class SimilarPostResponse(BaseModel):
    id: int
    title: str
    slug: str
    summary: Optional[str]
    similarity: float


class TagSuggestionRequest(BaseModel):
    title: str
    content: str


class PostDetailSuggestionRequest(BaseModel):
    content: str
    field: Optional[str] = "all"


class PostDetailSuggestionResponse(BaseModel):
    title: str
    slug: str
    summary: str
    tags: List[str]


@router.get("", response_model=PaginatedPostListResponse)
async def list_posts(
    published_only: bool = True,
    lang: Optional[str] = None,
    tag: Optional[str] = None,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("created_at", description="Field to sort by"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="Sort order"),
    search: Optional[str] = Query(None, description="Search in title and summary"),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """List posts with pagination, sorting, and search."""
    # Restrict access to drafts
    if not published_only:
        if not current_user or not current_user.is_admin:
            published_only = True

    # Build base query
    query = select(Post)
    if published_only:
        query = query.where(Post.published.is_(True))
    if lang:
        query = query.where(Post.language == lang)
    if tag:
        query = query.where(Post.tags.contains([tag]))

    # Apply search filter
    if search:
        search_term = f"%{search}%"
        query = query.where(
            (Post.title.ilike(search_term)) | (Post.summary.ilike(search_term))
        )

    # Get total count before pagination
    from sqlalchemy import func

    count_query = select(func.count()).select_from(query.subquery())
    total_raw = await db.scalar(count_query)
    total = int(total_raw) if total_raw is not None else 0

    # Apply sorting
    if hasattr(Post, sort_by):
        order_column = getattr(Post, sort_by)
        if sort_order == "desc":
            query = query.order_by(order_column.desc(), Post.id.desc())
        else:
            query = query.order_by(order_column.asc(), Post.id.asc())
    else:
        # Default to created_at desc if invalid sort field
        query = query.order_by(Post.created_at.desc(), Post.id.desc())

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    # Execute query
    result = await db.execute(query)
    posts = result.scalars().all()

    # Calculate total pages
    total_pages = ceil(total / page_size) if total > 0 else 1

    return PaginatedPostListResponse(
        items=[
            PostListResponse(
                id=p.id,
                title=p.title,
                slug=p.slug,
                summary=p.summary,
                image_url=p.display_image_url,
                language=p.language,
                published=p.published,
                tags=p.tags,
                created_at=p.created_at.isoformat(),
            )
            for p in posts
        ],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{id:int}", response_model=PostResponse)
async def get_post_by_id(
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Get a single post by ID."""
    result = await db.execute(select(Post).where(Post.id == id))
    post = result.scalar_one_or_none()

    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    # Check permissions for drafts
    if not post.published:
        if not current_user or not current_user.is_admin:
            raise HTTPException(status_code=404, detail="Post not found")

    return PostResponse(
        id=post.id,
        title=post.title,
        slug=post.slug,
        content=post.content,
        summary=post.summary,
        image_url=post.display_image_url,
        language=post.language,
        published=post.published,
        tags=post.tags,
        created_at=post.created_at.isoformat(),
        updated_at=post.updated_at.isoformat(),
    )


@router.get("/search/semantic")
async def semantic_search(
    q: str,
    lang: Optional[str] = "en",
    limit: int = 10,
    min_relevance: float = 0.3,  # Filter out low relevance
    db: AsyncSession = Depends(get_db),
):
    """
    Search posts using hybrid approach: Semantic (Vector) + Keyword (SQL ILIKE).
    """
    if not q or len(q.strip()) < 2:
        return []

    # 1. Vector Search
    vector_results = []
    try:
        query_embedding = await get_embedding(q)
        if query_embedding:
            vector_query = (
                select(
                    Post,
                    (1 - Post.embedding.cosine_distance(query_embedding)).label(
                        "relevance"
                    ),
                )
                .where(Post.published.is_(True))
                .where(Post.embedding.isnot(None))
            )
            if lang:
                vector_query = vector_query.where(Post.language == lang)

            # Fetch slightly more to allow for filtering/reranking
            vector_query = vector_query.order_by(text("relevance DESC")).limit(
                limit * 2
            )

            v_res = await db.execute(vector_query)
            vector_results = v_res.all()
    except Exception:
        # Fallback to keyword search if vector fails
        pass

    # 2. Keyword Search
    keyword_query = select(Post).where(Post.published.is_(True))
    if lang:
        keyword_query = keyword_query.where(Post.language == lang)

    search_term = f"%{q}%"
    keyword_query = keyword_query.where(
        (Post.title.ilike(search_term))
        | (Post.summary.ilike(search_term))
        | (Post.content.ilike(search_term))
    ).limit(limit)

    k_res = await db.execute(keyword_query)
    keyword_posts = k_res.scalars().all()

    # 3. Merge Results
    results_map = {}

    # Process Vector Results
    for post, relevance in vector_results:
        if relevance < min_relevance:
            continue
        results_map[post.id] = {
            "post": post,
            "relevance": float(relevance),
            "sources": {"vector"},
        }

    # Process Keyword Results
    for post in keyword_posts:
        if post.id in results_map:
            # Boost score if found in both
            results_map[post.id]["relevance"] = min(
                1.0, results_map[post.id]["relevance"] + 0.2
            )
            results_map[post.id]["sources"].add("keyword")
        else:
            # Add keyword-only match (give it a decent base score)
            results_map[post.id] = {
                "post": post,
                "relevance": 0.85,  # High confidence for exact match
                "sources": {"keyword"},
            }

    # Sort by relevance
    sorted_results = sorted(
        results_map.values(), key=lambda x: x["relevance"], reverse=True
    )[:limit]

    return [
        {
            "id": item["post"].id,
            "title": item["post"].title,
            "slug": item["post"].slug,
            "summary": item["post"].summary,
            "image_url": item["post"].display_image_url,
            "relevance": item["relevance"],
            # Debugging info could be returned if needed, but keeping schema clean for now
        }
        for item in sorted_results
    ]


@router.get("/{slug}", response_model=PostResponse)
async def get_post(
    slug: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Get a single post by slug."""
    result = await db.execute(select(Post).where(Post.slug == slug))
    post = result.scalar_one_or_none()

    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    # Check permissions for drafts
    if not post.published:
        if not current_user or not current_user.is_admin:
            raise HTTPException(status_code=404, detail="Post not found")

    return PostResponse(
        id=post.id,
        title=post.title,
        slug=post.slug,
        content=post.content,
        summary=post.summary,
        image_url=post.display_image_url,
        language=post.language,
        published=post.published,
        tags=post.tags,
        created_at=post.created_at.isoformat(),
        updated_at=post.updated_at.isoformat(),
    )


@router.post("", response_model=PostResponse)
async def create_post(
    post_data: PostCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """Create a new post with embedding."""
    # Generate embedding from title + content
    text_for_embedding = f"{post_data.title}\n\n{post_data.content}"
    embedding = await get_embedding(text_for_embedding)

    post = Post(
        title=post_data.title,
        slug=post_data.slug,
        content=post_data.content,
        summary=post_data.summary,
        image_url=post_data.image_url,
        language=post_data.language,
        published=post_data.published,
        tags=post_data.tags,
        embedding=embedding,
    )

    try:
        db.add(post)
        await db.commit()
    except Exception:
        await db.rollback()
        # Handle unique constraint on slug potentially
        import random

        post.slug = f"{post_data.slug}-{random.randint(1000, 9999)}"
        db.add(post)
        try:
            await db.commit()
            print("DEBUG: create_post retry commit success")
        except Exception as e2:
            print(f"DEBUG: create_post retry commit failed: {e2}")
            raise e2
    await db.refresh(post)

    return PostResponse(
        id=post.id,
        title=post.title,
        slug=post.slug,
        content=post.content,
        summary=post.summary,
        image_url=post.display_image_url,
        language=post.language,
        published=post.published,
        tags=post.tags,
        created_at=post.created_at.isoformat(),
        updated_at=post.updated_at.isoformat(),
    )


@router.get("/{slug}/similar", response_model=List[SimilarPostResponse])
async def get_similar_posts(
    slug: str,
    limit: int = 5,
    db: AsyncSession = Depends(get_db),
):
    """Find similar posts using vector similarity."""
    result = await db.execute(select(Post).where(Post.slug == slug))
    post = result.scalar_one_or_none()

    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    if post.embedding is None:
        return []

    # Find similar posts using cosine distance
    similar_query = (
        select(
            Post,
            Post.embedding.cosine_distance(post.embedding).label("distance"),
        )
        .where(Post.id != post.id)
        .where(Post.published.is_(True))
        .where(Post.language == post.language)
        .where(Post.embedding.isnot(None))
        .order_by("distance")
        .limit(limit)
    )

    result = await db.execute(similar_query)
    similar_posts = result.all()

    return [
        SimilarPostResponse(
            id=p.id,
            title=p.title,
            slug=p.slug,
            summary=p.summary,
            image_url=p.display_image_url,
            similarity=1 - distance,  # Convert distance to similarity
        )
        for p, distance in similar_posts
    ]


@router.post("/suggest-details")
async def suggest_post_details_endpoint(
    request: PostDetailSuggestionRequest,
    current_user: User = Depends(get_current_admin_user),
):
    """Suggest title, slug, and/or summary for a post using AI."""
    from app.services.ai import suggest_field, suggest_post_details

    if not request.field or request.field == "all":
        return await suggest_post_details(request.content, current_user.gemini_api_key)

    return await suggest_field(
        request.content, request.field, current_user.gemini_api_key
    )


@router.post("/suggest-tags")
async def suggest_tags_endpoint(
    request: TagSuggestionRequest, current_user: User = Depends(get_current_admin_user)
):
    """Suggest tags for a post using AI."""
    from app.services.ai import suggest_tags

    tags = await suggest_tags(
        request.title, request.content, current_user.gemini_api_key
    )
    return {"tags": tags}


class PostGenerationRequest(BaseModel):
    topic: str
    keywords: List[str] = []
    language: str = "en"


@router.post("/generate", response_model=PostResponse)
async def generate_post_endpoint(
    request: PostGenerationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Generate a full blog post using AI and save it as a draft.
    """
    from app.services.ai import generate_full_post

    generated_data = await generate_full_post(
        topic=request.topic,
        keywords=request.keywords,
        language=request.language,
        user_api_key=current_user.gemini_api_key,
    )

    if not generated_data:
        raise HTTPException(status_code=500, detail="Failed to generate post content")

    # Create the post structure
    # We need to generate an embedding for it too

    title = generated_data.get("title", "Untitled Post")
    content = generated_data.get("content", "")
    slug = generated_data.get("slug", "")
    summary = generated_data.get("summary", "")
    tags = generated_data.get("tags", [])

    # Ensure slug is unique-ish? For now let DB handle unique constraint error or append timestamp
    # But usually user will edit it.

    text_for_embedding = f"{title}\n\n{content}"
    embedding = await get_embedding(text_for_embedding)

    post = Post(
        title=title,
        slug=slug,
        content=content,
        summary=summary,
        language=request.language,
        published=False,  # Draft by default
        tags=tags,
        embedding=embedding,
    )

    try:
        db.add(post)
        await db.commit()
        await db.refresh(post)
    except Exception as e:
        print(f"DEBUG: create_post exception caught: {e}")
        await db.rollback()
        # Handle unique constraint on slug potentially
        import random

        post.slug = f"{slug}-{random.randint(1000, 9999)}"
        db.add(post)
        try:
            await db.commit()
            print("DEBUG: create_post retry commit success")
        except Exception as e2:
            print(f"DEBUG: create_post retry commit failed: {e2}")
            raise e2
        await db.refresh(post)

    return PostResponse(
        id=post.id,
        title=post.title,
        slug=post.slug,
        content=post.content,
        summary=post.summary,
        image_url=post.display_image_url,
        language=post.language,
        published=post.published,
        tags=post.tags,
        created_at=post.created_at.isoformat(),
        updated_at=post.updated_at.isoformat(),
    )


@router.put("/{id:int}", response_model=PostResponse)
async def update_post_by_id(
    id: int,
    post_data: PostUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """Update a post by ID."""
    result = await db.execute(select(Post).where(Post.id == id))
    post = result.scalar_one_or_none()

    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    update_embedding = False
    if post_data.title is not None:
        post.title = post_data.title
        update_embedding = True
    if post_data.content is not None:
        post.content = post_data.content
        update_embedding = True
    if post_data.summary is not None:
        post.summary = post_data.summary
    if post_data.image_url is not None:
        post.image_url = post_data.image_url
    if post_data.language is not None:
        post.language = post_data.language
    if post_data.published is not None:
        post.published = post_data.published
    if post_data.tags is not None:
        post.tags = post_data.tags

    # Regenerate embedding if content changed
    if update_embedding:
        text_for_embedding = f"{post.title}\n\n{post.content}"
        post.embedding = await get_embedding(text_for_embedding)

    await db.commit()
    await db.refresh(post)

    return PostResponse(
        id=post.id,
        title=post.title,
        slug=post.slug,
        content=post.content,
        summary=post.summary,
        image_url=post.display_image_url,
        language=post.language,
        published=post.published,
        tags=post.tags,
        created_at=post.created_at.isoformat(),
        updated_at=post.updated_at.isoformat(),
    )


@router.delete("/{id:int}")
async def delete_post_by_id(
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """Delete a post by ID."""
    result = await db.execute(select(Post).where(Post.id == id))
    post = result.scalar_one_or_none()

    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    await db.delete(post)
    await db.commit()

    return {"message": "Post deleted"}


@router.put("/{post_id}/image", response_model=PostResponse)
async def upload_post_image(
    post_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Upload an image for a blog post.
    """
    result = await db.execute(select(Post).where(Post.id == post_id))
    post = result.scalar_one_or_none()

    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    # Read file content
    content = await file.read()

    # Update post
    post.image_blob = content
    post.image_type = file.content_type

    # Clear external URL if a file is uploaded
    post.image_url = None

    await db.commit()
    await db.refresh(post)
    return PostResponse(
        id=post.id,
        title=post.title,
        slug=post.slug,
        content=post.content,
        summary=post.summary,
        # image_url handled by validator/alias from display_image_url property
        image_url=post.display_image_url,
        language=post.language,
        published=post.published,
        tags=post.tags,
        created_at=post.created_at.isoformat(),
        updated_at=post.updated_at.isoformat(),
    )


@router.get("/{post_id}/image")
async def get_post_image(
    post_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Get the image for a blog post.
    """
    from sqlalchemy.orm import undefer

    result = await db.execute(
        select(Post).options(undefer(Post.image_blob)).where(Post.id == post_id)
    )
    post = result.scalar_one_or_none()

    if not post or not post.image_blob:
        raise HTTPException(status_code=404, detail="Image not found")

    from io import BytesIO
    from starlette.responses import StreamingResponse

    return StreamingResponse(
        BytesIO(post.image_blob), media_type=post.image_type or "image/jpeg"
    )
