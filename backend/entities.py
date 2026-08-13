"""
Entity detection engine.

Two layers:
1. Regex patterns for common PII / sensitive data types (India-first, plus
   common international formats).
2. A word-level matcher that takes a flat list of OCR/PDF "words" (each with
   its own bounding box) and returns which words are covered by a detected
   entity, so callers can draw a precise redaction box instead of guessing.
"""
import re
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional


@dataclass
class EntityPattern:
    key: str
    label: str
    pattern: str
    priority: int = 0  # higher wins on overlap
    validator: Optional[callable] = None


def _luhn_ok(number: str) -> bool:
    digits = [int(d) for d in re.sub(r"\D", "", number)]
    if len(digits) < 12:
        return False
    checksum = 0
    parity = len(digits) % 2
    for i, d in enumerate(digits):
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


PATTERNS: List[EntityPattern] = [
    EntityPattern("email", "Email", r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", priority=5),
    EntityPattern("pan", "PAN", r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", priority=6),
    EntityPattern("aadhaar", "Aadhaar", r"\b\d{4}\s?\d{4}\s?\d{4}\b", priority=4),
    EntityPattern("gstin", "GSTIN", r"\b\d{2}[A-Z]{5}\d{4}[A-Z]\d[Z][A-Z\d]\b", priority=6),
    EntityPattern("passport_in", "Passport", r"\b[A-PR-WYa-pr-wy][1-9]\d\s?\d{4}[1-9]\b", priority=5),
    EntityPattern("credit_card", "Card Number", r"\b(?:\d[ -]?){13,19}\b", priority=7,
                  validator=_luhn_ok),
    EntityPattern("ssn", "SSN", r"\b\d{3}-\d{2}-\d{4}\b", priority=6),
    EntityPattern("ifsc", "IFSC", r"\b[A-Z]{4}0[A-Z0-9]{6}\b", priority=4),
    EntityPattern("phone", "Phone", r"(?:\+?\d{1,3}[-.\s]?)?(?:\(\d{2,4}\)[-.\s]?)?\d{3,5}[-.\s]?\d{3,5}\b", priority=2),
    EntityPattern("ip", "IP Address", r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b", priority=3),
    EntityPattern("dob", "Date", r"\b(?:0?[1-9]|[12]\d|3[01])[/-](?:0?[1-9]|1[0-2])[/-](?:\d{4}|\d{2})\b", priority=1),
]

_DEFAULT_ENABLED = {p.key for p in PATTERNS}


def compiled_patterns(enabled_keys: Optional[List[str]] = None):
    keys = set(enabled_keys) if enabled_keys else _DEFAULT_ENABLED
    return [(p, re.compile(p.pattern)) for p in PATTERNS if p.key in keys]


@dataclass
class Word:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    page: int = 0


@dataclass
class Match:
    key: str
    label: str
    text: str
    page: int
    boxes: List[Tuple[float, float, float, float]] = field(default_factory=list)


def redact_text_only(text: str, enabled_keys: Optional[List[str]] = None) -> Tuple[str, List[Dict]]:
    """Simple string-in string-out redaction for the paste-text tab."""
    found = []
    ordered = sorted(compiled_patterns(enabled_keys), key=lambda pr: -pr[0].priority)
    for pattern, rx in ordered:
        def _sub(m, pattern=pattern):
            if pattern.validator and not pattern.validator(m.group(0)):
                return m.group(0)
            found.append({"type": pattern.key, "label": pattern.label, "value": m.group(0)})
            return f"[{pattern.label.upper()} REDACTED]"
        text = rx.sub(_sub, text)
    return text, found


def find_matches_in_words(words: List[Word], enabled_keys: Optional[List[str]] = None) -> List[Match]:
    """
    Reconstructs a text stream from `words` (which each carry a bbox),
    runs every enabled entity pattern against it, then maps each match's
    character span back onto the covering words so we know exactly which
    boxes to blackout.
    """
    if not words:
        return []

    # Build the joined text + an offset table: char index -> word index
    joined_parts = []
    offset_to_word = []
    cursor = 0
    for i, w in enumerate(words):
        joined_parts.append(w.text)
        for _ in range(len(w.text)):
            offset_to_word.append(i)
        joined_parts.append(" ")
        offset_to_word.append(-1)  # space
        cursor += len(w.text) + 1
    joined = "".join(joined_parts)

    claimed = [False] * len(words)  # avoid double-claiming credit card digits as phone etc
    matches: List[Match] = []
    patterns_sorted = sorted(compiled_patterns(enabled_keys), key=lambda pr: -pr[0].priority)

    for pattern, rx in patterns_sorted:
        for m in rx.finditer(joined):
            if pattern.validator and not pattern.validator(m.group(0)):
                continue
            start, end = m.start(), m.end()
            word_idxs = sorted({offset_to_word[i] for i in range(start, min(end, len(offset_to_word)))
                                 if offset_to_word[i] != -1})
            word_idxs = [wi for wi in word_idxs if not claimed[wi]]
            if not word_idxs:
                continue
            for wi in word_idxs:
                claimed[wi] = True
            boxes = [(words[wi].x0, words[wi].y0, words[wi].x1, words[wi].y1) for wi in word_idxs]
            matches.append(Match(
                key=pattern.key,
                label=pattern.label,
                text=m.group(0),
                page=words[word_idxs[0]].page,
                boxes=boxes,
            ))
    return matches


ENTITY_CATALOG = [{"key": p.key, "label": p.label} for p in PATTERNS]
