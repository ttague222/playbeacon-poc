"""
Thumbnail utility for heuristic validation.
"""
import re

BAD_THUMB_PATTERNS = [
    re.compile(r"placeholder", re.I),
    re.compile(r"noplaceholder", re.I),
    re.compile(r"assetdelivery", re.I),
    re.compile(r"127\.0\.0\.1", re.I),
    re.compile(r"example", re.I),
]


def is_bad_thumbnail(url: str) -> bool:
    if not url:
        return True
    lower = url.lower()
    for pat in BAD_THUMB_PATTERNS:
        if pat.search(lower):
            return True
    return False
