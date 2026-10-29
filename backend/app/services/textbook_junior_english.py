"""Reviewed grade 7–9 English contents, with selectable Section A/B."""
import json
import re
from functools import lru_cache
from pathlib import Path

from app.services.textbook_english import topic_chapters_from_review
from app.services.textbook_english_sections import expand_section_chapters, section_directory_from_review


@lru_cache(maxsize=1)
def reviewed_junior_english_directories():
    path = Path(__file__).resolve().parents[1]/'data'/'junior_english_directories.json'
    return json.loads(path.read_text(encoding='utf8'))


def junior_english_topic_chapters(digest, texts):
    return topic_chapters_from_review(reviewed_junior_english_directories().get(digest), texts)


def expand_junior_english_chapters(digest, chapters, texts):
    return expand_section_chapters(reviewed_junior_english_directories().get(digest), chapters, texts, junior=True)


def _unit_key(title):
    match = re.match(r'^(starter\s+)?unit\s*(\d+)\b', title, re.I)
    return (bool(match[1]), int(match[2])) if match else None


def junior_english_directory(book, chapters):
    """Display units and selectable Section A/B, without task subheadings."""
    review = reviewed_junior_english_directories().get(book.sha256)
    if not review:
        return None
    return section_directory_from_review(review, chapters, _unit_key, junior=True)
