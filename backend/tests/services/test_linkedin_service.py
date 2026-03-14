import pytest
from unittest.mock import MagicMock, patch
from app.services.linkedin import LinkedInService


@pytest.fixture
def service():
    svc = LinkedInService()
    svc._client = None
    return svc


@pytest.mark.asyncio
async def test_get_client_missing_credentials(service, mocker):
    mocker.patch("app.services.linkedin.settings.linkedin_email", "")
    mocker.patch("app.services.linkedin.settings.linkedin_password", "")

    with pytest.raises(ValueError, match="LinkedIn credentials are not configured"):
        service._get_client()


@pytest.mark.asyncio
async def test_get_client_initializes_on_first_call(service, mocker):
    mocker.patch("app.services.linkedin.settings.linkedin_email", "test@test.com")
    mocker.patch("app.services.linkedin.settings.linkedin_password", "pass")

    mock_linkedin = MagicMock()
    with (
        patch("linkedin_api.Linkedin", return_value=mock_linkedin) as mock_cls,
        patch("os.listdir", return_value=[]),
    ):
        client = service._get_client()
        assert client is mock_linkedin
        mock_cls.assert_called_once_with(
            "test@test.com",
            "pass",
            cookies=None,
            authenticate=False,
            cookies_dir="/tmp/linkedin_cookies",
        )


@pytest.mark.asyncio
async def test_get_client_reuses_existing(service, mocker):
    mock_client = MagicMock()
    service._client = mock_client
    assert service._get_client() is mock_client


@pytest.mark.asyncio
async def test_get_public_id_missing(service, mocker):
    mocker.patch("app.services.linkedin.settings.linkedin_public_id", "")

    with pytest.raises(ValueError, match="LinkedIn public ID is not configured"):
        service._get_public_id()


@pytest.mark.asyncio
async def test_get_public_id_configured(service, mocker):
    mocker.patch("app.services.linkedin.settings.linkedin_public_id", "john-doe")
    assert service._get_public_id() == "john-doe"


@pytest.mark.asyncio
async def test_fetch_posts_success(service, mocker):
    mocker.patch("app.services.linkedin.settings.linkedin_public_id", "john-doe")

    mock_client = MagicMock()
    mock_client.get_profile_posts.return_value = [
        {
            "commentary": {"text": "Hello LinkedIn!"},
            "content": {},
            "updateMetadata": {"urn": "urn:123"},
        },
        {
            "commentary": {"text": "Second post"},
            "content": {},
            "updateMetadata": {"urn": "urn:456"},
        },
    ]
    service._client = mock_client

    posts = await service.fetch_posts(count=10)
    assert len(posts) == 2
    assert posts[0]["content"] == "Hello LinkedIn!"
    assert posts[0]["urn"] == "urn:123"
    mock_client.get_profile_posts.assert_called_once_with(
        public_id="john-doe",
        post_count=10,
    )


@pytest.mark.asyncio
async def test_fetch_posts_filters_empty(service, mocker):
    mocker.patch("app.services.linkedin.settings.linkedin_public_id", "john-doe")

    mock_client = MagicMock()
    mock_client.get_profile_posts.return_value = [
        {"commentary": {"text": ""}, "content": {}},
        {"commentary": {"text": "Valid post"}, "content": {}},
    ]
    service._client = mock_client

    posts = await service.fetch_posts()
    assert len(posts) == 1
    assert posts[0]["content"] == "Valid post"


@pytest.mark.asyncio
async def test_fetch_posts_api_error(service, mocker):
    mocker.patch("app.services.linkedin.settings.linkedin_public_id", "john-doe")

    mock_client = MagicMock()
    mock_client.get_profile_posts.side_effect = Exception("API down")
    service._client = mock_client

    with pytest.raises(RuntimeError, match="Failed to fetch LinkedIn posts"):
        await service.fetch_posts()


@pytest.mark.asyncio
async def test_sync_profile_success(service, mocker):
    mocker.patch("app.services.linkedin.settings.linkedin_public_id", "john-doe")

    mock_client = MagicMock()
    mock_client.get_profile.return_value = {"firstName": "John", "lastName": "Doe"}
    service._client = mock_client

    profile = await service.sync_profile()
    assert profile["firstName"] == "John"
    mock_client.get_profile.assert_called_once_with(public_id="john-doe")


@pytest.mark.asyncio
async def test_sync_profile_error(service, mocker):
    mocker.patch("app.services.linkedin.settings.linkedin_public_id", "john-doe")

    mock_client = MagicMock()
    mock_client.get_profile.side_effect = Exception("Network error")
    service._client = mock_client

    with pytest.raises(RuntimeError, match="Failed to fetch LinkedIn profile"):
        await service.sync_profile()


def test_parse_post_with_commentary():
    post = LinkedInService._parse_post(
        {
            "commentary": {"text": "Test post content"},
            "content": {},
            "updateMetadata": {"urn": "urn:li:activity:123"},
        }
    )
    assert post is not None
    assert post["content"] == "Test post content"
    assert post["urn"] == "urn:li:activity:123"


def test_parse_post_with_string_commentary():
    post = LinkedInService._parse_post(
        {
            "commentary": "Direct text content",
            "content": {},
        }
    )
    assert post is not None
    assert post["content"] == "Direct text content"


def test_parse_post_empty_content_returns_none():
    post = LinkedInService._parse_post(
        {
            "commentary": {"text": ""},
            "content": {},
        }
    )
    assert post is None


def test_parse_post_malformed_data():
    post = LinkedInService._parse_post({})
    assert post is None


def test_parse_post_with_star_urn():
    """Cover line 102: *updateMetadata URN format."""
    post = LinkedInService._parse_post(
        {
            "*updateMetadata": "urn:li:activity:star123",
            "commentary": {"text": "Post with star URN"},
            "content": {},
        }
    )
    assert post is not None
    assert post["urn"] == "urn:li:activity:star123"


def test_parse_post_with_article_title_fallback():
    """Cover line 121: article title fallback when no commentary."""
    post = LinkedInService._parse_post(
        {
            "content": {"article": {"title": "Article Title Fallback"}},
        }
    )
    assert post is not None
    assert post["content"] == "Article Title Fallback"


def test_parse_post_with_text_field_fallback():
    """Cover line 113: text field fallback when no commentary."""
    post = LinkedInService._parse_post(
        {
            "text": "Fallback text content",
            "content": {},
        }
    )
    assert post is not None
    assert post["content"] == "Fallback text content"


def test_parse_post_with_image_extraction():
    """Cover lines 128-134: image extraction from attributes."""
    post = LinkedInService._parse_post(
        {
            "commentary": {"text": "Post with image"},
            "content": {
                "images": [
                    {
                        "attributes": [
                            {
                                "vectorImage": {
                                    "rootUrl": "https://media.licdn.com/image.jpg"
                                }
                            }
                        ]
                    }
                ]
            },
        }
    )
    assert post is not None
    assert post["image_url"] == "https://media.licdn.com/image.jpg"


def test_parse_post_with_image_no_attributes():
    """Cover image branch with empty attributes."""
    post = LinkedInService._parse_post(
        {
            "commentary": {"text": "Post with image but no attrs"},
            "content": {"images": [{"attributes": []}]},
        }
    )
    assert post is not None
    assert post["image_url"] is None


def test_parse_post_with_image_non_dict():
    """Cover image branch where image is not a dict."""
    post = LinkedInService._parse_post(
        {
            "commentary": {"text": "Post with weird image"},
            "content": {"images": ["not-a-dict"]},
        }
    )
    assert post is not None
    assert post["image_url"] is None


def test_parse_post_exception_handling():
    """Cover lines 144-146: exception in parse."""
    # Force an exception by passing a non-dict
    post = LinkedInService._parse_post(None)
    assert post is None
