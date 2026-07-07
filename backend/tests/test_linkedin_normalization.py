"""
Unit tests for the pure LinkedIn text-normalization helpers.
No I/O, no network, no fixtures required.
"""

import pytest

from app.services.linkedin import extract_hashtags, normalize_linkedin_text

# ── normalize_linkedin_text ──────────────────────────────────────────────────

NORMALIZE_CASES = [
    (
        "empty_string",
        "",
        "",
    ),
    (
        "whitespace_only",
        "   \n\t  ",
        "",
    ),
    (
        "real_dirty_sample",
        # verbatim from spec: zero-width char + hashtag label lines
        "…noise?\u200b\nhashtag\n#EngineeringManagement \nhashtag\n#SoftwareArchitecture",
        "…noise?\n#EngineeringManagement \n#SoftwareArchitecture",
    ),
    (
        "zero_width_chars_removed",
        "hello\u200b\u200e\u200f\ufeffworld",
        "helloworld",
    ),
    (
        "nbsp_becomes_space",
        "hello\u00a0world",
        "hello world",
    ),
    (
        "hashtag_label_removed",
        "some text\nhashtag\n#Python\nmore text",
        "some text\n#Python\nmore text",
    ),
    (
        "hashtag_label_with_surrounding_spaces",
        "text\n  hashtag  \n#Go\nend",
        "text\n#Go\nend",
    ),
    (
        "excess_newlines_collapsed",
        "para1\n\n\n\n\npara2",
        "para1\n\npara2",
    ),
    (
        "normal_paragraph_break_preserved",
        "para1\n\npara2",
        "para1\n\npara2",
    ),
    (
        "leading_trailing_whitespace_stripped",
        "  \n  hello  \n  ",
        "hello",
    ),
    (
        "no_hashtag_label_plain_text",
        "Just a normal post.",
        "Just a normal post.",
    ),
]


@pytest.mark.parametrize(
    "case_id,text,expected",
    NORMALIZE_CASES,
    ids=[c[0] for c in NORMALIZE_CASES],
)
def test_normalize_linkedin_text(case_id: str, text: str, expected: str) -> None:
    assert normalize_linkedin_text(text) == expected


def test_normalize_no_zero_width_in_output() -> None:
    """Explicit assertion: none of the zero-width chars survive."""
    dirty = "a\u200bb\u200ec\u200fd\ufeffe"
    result = normalize_linkedin_text(dirty)
    for ch in "\u200b\u200e\u200f\ufeff":
        assert ch not in result


def test_normalize_real_sample_no_hashtag_token() -> None:
    """The literal word 'hashtag' must not appear in the cleaned output."""
    raw = "…noise?\u200b\nhashtag\n#EngineeringManagement \nhashtag\n#SoftwareArchitecture"
    result = normalize_linkedin_text(raw)
    assert "hashtag" not in result.split()
    assert "#EngineeringManagement" in result
    assert "#SoftwareArchitecture" in result


# ── extract_hashtags ─────────────────────────────────────────────────────────

EXTRACT_CASES = [
    (
        "empty_string",
        "",
        [],
    ),
    (
        "whitespace_only",
        "   ",
        [],
    ),
    (
        "no_hashtags",
        "Just plain text, no tags here.",
        [],
    ),
    (
        "real_sample_two_tags",
        "#EngineeringManagement #SoftwareArchitecture",
        ["EngineeringManagement", "SoftwareArchitecture"],
    ),
    (
        "strips_hash_prefix",
        "#Python is great",
        ["Python"],
    ),
    (
        "dedup_case_insensitive_first_seen_casing",
        "#Python #python #PYTHON",
        ["Python"],
    ),
    (
        "capped_at_five",
        "#A #B #C #D #E #F #G",
        ["A", "B", "C", "D", "E"],
    ),
    (
        "first_seen_order_preserved",
        "#Zebra #Apple #Mango",
        ["Zebra", "Apple", "Mango"],
    ),
    (
        "hash_only_not_matched",
        "# not a tag",
        [],
    ),
    (
        "numeric_start_not_matched",
        "#123tag",
        [],
    ),
    (
        "mixed_valid_and_invalid",
        "#Valid #123bad #AlsoValid",
        ["Valid", "AlsoValid"],
    ),
]


@pytest.mark.parametrize(
    "case_id,text,expected",
    EXTRACT_CASES,
    ids=[c[0] for c in EXTRACT_CASES],
)
def test_extract_hashtags(case_id: str, text: str, expected: list[str]) -> None:
    assert extract_hashtags(text) == expected
