"""Tests for the CV years API endpoint."""
import json
import pytest
from unittest.mock import patch


# ─── Unit tests for _extract_years_from_profile ───


class TestExtractYearsFromProfile:
    """Unit tests for the year extraction helper."""

    def test_extracts_years_from_valid_profile(self, tmp_path):
        """Should extract distinct years from experience startDate fields."""
        from app.api.years import _extract_years_from_profile

        profile = {
            "experience": [
                {"title": "Dev", "startDate": "Mar 2025"},
                {"title": "Dev", "startDate": "Jan 2024"},
                {"title": "Dev", "startDate": "Apr 2014"},
                {"title": "Dev", "startDate": "Sep 2009"},
            ]
        }
        fp = tmp_path / "profile.json"
        fp.write_text(json.dumps(profile))

        years = _extract_years_from_profile(str(fp))
        assert years == {2025, 2024, 2014, 2009}

    def test_returns_empty_for_missing_file(self, tmp_path):
        """Should return empty set when file does not exist."""
        from app.api.years import _extract_years_from_profile

        years = _extract_years_from_profile(str(tmp_path / "not_exists.json"))
        assert years == set()

    def test_returns_empty_for_invalid_json(self, tmp_path):
        """Should return empty set for broken JSON."""
        from app.api.years import _extract_years_from_profile

        fp = tmp_path / "broken.json"
        fp.write_text("{bad json")

        years = _extract_years_from_profile(str(fp))
        assert years == set()

    def test_returns_empty_for_no_experience(self, tmp_path):
        """Should return empty set when no experience key exists."""
        from app.api.years import _extract_years_from_profile

        fp = tmp_path / "empty.json"
        fp.write_text(json.dumps({"name": "Test"}))

        years = _extract_years_from_profile(str(fp))
        assert years == set()

    def test_handles_missing_start_date(self, tmp_path):
        """Should skip entries without startDate."""
        from app.api.years import _extract_years_from_profile

        profile = {
            "experience": [
                {"title": "Dev"},
                {"title": "Dev", "startDate": "Mar 2025"},
            ]
        }
        fp = tmp_path / "profile.json"
        fp.write_text(json.dumps(profile))

        years = _extract_years_from_profile(str(fp))
        assert years == {2025}

    def test_deduplicates_years(self, tmp_path):
        """Should return distinct years even with duplicates."""
        from app.api.years import _extract_years_from_profile

        profile = {
            "experience": [
                {"title": "Dev1", "startDate": "Jan 2024"},
                {"title": "Dev2", "startDate": "Jun 2024"},
                {"title": "Dev3", "startDate": "Dec 2024"},
            ]
        }
        fp = tmp_path / "profile.json"
        fp.write_text(json.dumps(profile))

        years = _extract_years_from_profile(str(fp))
        assert years == {2024}

    def test_handles_non_standard_date_formats(self, tmp_path):
        """Should extract year from various date string formats."""
        from app.api.years import _extract_years_from_profile

        profile = {
            "experience": [
                {"title": "Dev", "startDate": "2020"},
                {"title": "Dev", "startDate": "Jun 2004 - Aug 2005 · 1 yr 3 mos"},
                {"title": "Dev", "startDate": "Tiraspol, Transnistria autonomous territorial unit, Moldova"},
            ]
        }
        fp = tmp_path / "profile.json"
        fp.write_text(json.dumps(profile))

        years = _extract_years_from_profile(str(fp))
        assert 2020 in years
        assert 2004 in years


# ─── API endpoint tests (no DB needed) ───


@pytest.mark.asyncio
class TestYearsEndpoint:
    """Integration tests for GET /api/app/cv/years."""

    @pytest.fixture
    def _client(self):
        """Lightweight async client without DB dependency."""
        from app.main import app
        from httpx import AsyncClient, ASGITransport
        import asyncio

        async def _make_client():
            transport = ASGITransport(app=app)
            return AsyncClient(transport=transport, base_url="http://test")

        return asyncio.get_event_loop().run_until_complete(_make_client())

    async def test_returns_years_sorted_descending(self, tmp_path):
        """Should return years in descending order."""
        from app.main import app
        from httpx import AsyncClient, ASGITransport

        profile = {
            "experience": [
                {"title": "Dev", "startDate": "Jan 2021"},
                {"title": "Dev", "startDate": "Mar 2025"},
                {"title": "Dev", "startDate": "Apr 2014"},
            ]
        }
        for lang in ("en", "de"):
            fp = tmp_path / f"profile_data_{lang}.json"
            fp.write_text(json.dumps(profile))

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            with patch("app.api.years.PROFILE_DATA_DIR", str(tmp_path)):
                response = await ac.get("/api/app/cv/years")

        assert response.status_code == 200
        data = response.json()
        assert data["years"] == [2025, 2021, 2014]

    async def test_returns_404_when_no_data(self, tmp_path):
        """Should return 404 when no profile files have experience data."""
        from app.main import app
        from httpx import AsyncClient, ASGITransport

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            with patch("app.api.years.PROFILE_DATA_DIR", str(tmp_path / "nonexistent")):
                response = await ac.get("/api/app/cv/years")

        assert response.status_code == 404

    async def test_years_are_integers(self, tmp_path):
        """All returned years should be integers."""
        from app.main import app
        from httpx import AsyncClient, ASGITransport

        profile = {
            "experience": [
                {"title": "Dev", "startDate": "Mar 2025"},
                {"title": "Dev", "startDate": "Sep 2009"},
            ]
        }
        for lang in ("en", "de"):
            fp = tmp_path / f"profile_data_{lang}.json"
            fp.write_text(json.dumps(profile))

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            with patch("app.api.years.PROFILE_DATA_DIR", str(tmp_path)):
                response = await ac.get("/api/app/cv/years")

        assert response.status_code == 200
        for year in response.json()["years"]:
            assert isinstance(year, int)

    async def test_years_have_no_duplicates(self, tmp_path):
        """Years should be unique even when both language files have overlapping data."""
        from app.main import app
        from httpx import AsyncClient, ASGITransport

        profile_en = {
            "experience": [
                {"title": "Dev", "startDate": "Jan 2024"},
                {"title": "Dev", "startDate": "Mar 2025"},
            ]
        }
        profile_de = {
            "experience": [
                {"title": "Dev", "startDate": "Mär 2025"},
                {"title": "Dev", "startDate": "Jan 2024"},
            ]
        }
        (tmp_path / "profile_data_en.json").write_text(json.dumps(profile_en))
        (tmp_path / "profile_data_de.json").write_text(json.dumps(profile_de))

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            with patch("app.api.years.PROFILE_DATA_DIR", str(tmp_path)):
                response = await ac.get("/api/app/cv/years")

        years = response.json()["years"]
        assert len(years) == len(set(years))

    async def test_merges_years_from_both_languages(self, tmp_path):
        """Should union years from EN and DE profile files."""
        from app.main import app
        from httpx import AsyncClient, ASGITransport

        profile_en = {
            "experience": [
                {"title": "Dev", "startDate": "Jan 2024"},
            ]
        }
        profile_de = {
            "experience": [
                {"title": "Dev", "startDate": "Jun 2004"},
            ]
        }
        (tmp_path / "profile_data_en.json").write_text(json.dumps(profile_en))
        (tmp_path / "profile_data_de.json").write_text(json.dumps(profile_de))

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            with patch("app.api.years.PROFILE_DATA_DIR", str(tmp_path)):
                response = await ac.get("/api/app/cv/years")

        assert response.status_code == 200
        years = response.json()["years"]
        assert 2024 in years
        assert 2004 in years
