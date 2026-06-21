import re

_MAX_SEGMENTS = 15


def segment_text(text: str) -> list[str]:
    if not text or not text.strip():
        return []
    text = text.strip()
    text = _insert_breaks_for_arabic(text)
    raw = re.split(r'\n+|(?<=[.!?؟])\s+', text)
    segments = [s.strip() for s in raw if s.strip()]
    if not segments:
        return [text]
    if len(segments) > _MAX_SEGMENTS:
        segments = segments[:_MAX_SEGMENTS - 1] + [" ".join(segments[_MAX_SEGMENTS - 1:])]
    return segments


def _insert_breaks_for_arabic(text: str) -> str:
    text = re.sub(r'(\d+)(و[\u0621-\u064A\u0660-\u0669])', r'\1. \2', text)
    text = re.sub(r'(\d+)(ف[\u0621-\u064A\u0660-\u0669])', r'\1. \2', text)
    text = re.sub(r'(\d+)(ب[\u0621-\u064A\u0660-\u0669])', r'\1. \2', text)
    text = re.sub(r'(\d+)(ل[\u0621-\u064A\u0660-\u0669])', r'\1. \2', text)
    text = re.sub(r'(\d+)(?:\s*)(و)\s*', r'\1. \2 ', text)
    text = re.sub(r'(\d+)(?:\s*)(ف)(?!ي\s+الاسبوع|ي\s+الشهر|ي\s+السنة|ي\s+اليوم)', r'\1. \2 ', text)
    return text
