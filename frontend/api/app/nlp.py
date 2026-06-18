import re
from typing import Iterable
from .heuristics import normalize_number, normalize_text

try:
    import spacy
except ImportError:  # pragma: no cover
    spacy = None


_nlp = None


def get_nlp():
    global _nlp
    if _nlp is not None:
        return _nlp
    if spacy is None:
        return None
    try:
        _nlp = spacy.load("en_core_web_sm")
    except OSError:
        _nlp = spacy.blank("en")
    return _nlp


def extract_numbers(text: str) -> list[float]:
    text = normalize_text(text)
    pattern_numbers = []
    for match in re.findall(r"(?:[$€£])?\s*\d+(?:,\d{3})*(?:\.\d+)?[kKmM]?", text):
        value = normalize_number(match)
        if value is not None:
            pattern_numbers.append(value)

    nlp = get_nlp()
    if nlp is None:
        return _dedupe(pattern_numbers)

    doc = nlp(text)
    token_numbers = []
    for token in doc:
        if token.like_num:
            value = normalize_number(token.text)
            if value is not None:
                token_numbers.append(value)

    return _dedupe([*pattern_numbers, *token_numbers])


def extract_entities(text: str) -> list[dict]:
    """Use spaCy NER to detect financial entities (MONEY, DATE, CARDINAL, etc.)"""
    nlp = get_nlp()
    if nlp is None:
        return []
    try:
        doc = nlp(text)
        entities = []
        for ent in doc.ents:
            if ent.label_ in ("MONEY", "DATE", "CARDINAL", "PERCENT", "QUANTITY", "TIME"):
                entities.append({"text": ent.text, "label": ent.label_})
        return entities
    except Exception:
        return []


def _dedupe(values: Iterable[float]) -> list[float]:
    seen = set()
    result = []
    for value in values:
        key = round(float(value), 4)
        if key not in seen:
            seen.add(key)
            result.append(float(value))
    return result
