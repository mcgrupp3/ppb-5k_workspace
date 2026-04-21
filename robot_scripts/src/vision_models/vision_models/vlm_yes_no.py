"""Parse VLM free-text answers into a yes/no decision."""
from __future__ import annotations

import re
from typing import Optional, Tuple

# Order matters: scan for clear negatives before positives if both appear
_NO_WORDS = re.compile(
    r"\b(no|nope|not\s+present|not\s+visible|absent|false|negative|isn't|is\s+not)\b",
    re.IGNORECASE,
)
_YES_WORDS = re.compile(
    r"\b(yes|yeah|yep|present|visible|there\s+is|true|positive|affirmative)\b",
    re.IGNORECASE,
)


def parse_yes_no(answer: str) -> Tuple[Optional[bool], str]:
    """
    Return (True/False, reason). None if ambiguous.

    Prefer an explicit yes/no at the start; otherwise first strong keyword match.
    """
    if not answer or not answer.strip():
        return None, 'empty answer'

    text = answer.strip()
    lower = text.lower()

    # First line often holds the direct answer
    first = text.splitlines()[0].strip().lower()
    first = re.sub(r"^[\s\"'`]+|[\s\"'`]+$", "", first)

    if first in ("yes", "y"):
        return True, "exact yes"
    if first in ("no", "n"):
        return False, "exact no"

    # Leading yes/no with punctuation
    m = re.match(r"^(yes|no)\b", lower)
    if m:
        return m.group(1) == "yes", "leading yes/no"

    no_m = _NO_WORDS.search(text)
    yes_m = _YES_WORDS.search(text)
    if yes_m and not no_m:
        return True, f"keyword at {yes_m.start()}"
    if no_m and not yes_m:
        return False, f"keyword at {no_m.start()}"
    if yes_m and no_m:
        if yes_m.start() < no_m.start():
            return True, "yes keyword before no keyword"
        if no_m.start() < yes_m.start():
            return False, "no keyword before yes keyword"

    return None, "could not parse yes/no from model output"