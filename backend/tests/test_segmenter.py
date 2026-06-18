import pytest
from app.segmenter import segment_text


class TestSegmentText:
    def test_empty_text(self):
        assert segment_text("") == []

    def test_whitespace_only(self):
        assert segment_text("   ") == []

    def test_single_sentence(self):
        result = segment_text("I earn 5000 per month")
        assert result == ["I earn 5000 per month"]

    def test_multiple_english_sentences(self):
        result = segment_text("I earn 5000. My rent is 1500. I have 10000 saved.")
        assert result == ["I earn 5000.", "My rent is 1500.", "I have 10000 saved."]

    def test_newline_separator(self):
        result = segment_text("salary 5000\nrent 1500\nsavings 10000")
        assert len(result) == 3

    def test_arabic_text(self):
        result = segment_text("راتبي 5000. مصاريفي 1500. عندي 10000 مدخرات.")
        assert len(result) == 3

    def test_arabic_question_mark(self):
        result = segment_text("عايز عربية؟ معايا 5000")
        assert len(result) == 2

    def test_attached_numbers_no_break(self):
        result = segment_text("عايز عربية 5000وقبض 2000")
        assert len(result) == 2

    def test_max_segments_enforced(self):
        text = ". ".join([f"sentence {i}" for i in range(20)])
        result = segment_text(text)
        assert len(result) <= 15

    def test_no_sentence_breaks(self):
        result = segment_text("hello world foo bar baz")
        assert result == ["hello world foo bar baz"]
