from app.nlp import extract_numbers


class TestExtractNumbers:
    def test_basic_numbers(self):
        result = extract_numbers("I have 5000 dollars")
        assert 5000.0 in result

    def test_multiple_numbers(self):
        result = extract_numbers("earn 6500 spend 4200 save 8000")
        assert 6500.0 in result
        assert 4200.0 in result
        assert 8000.0 in result

    def test_with_k(self):
        result = extract_numbers("5k income")
        assert 5000.0 in result

    def test_empty_text(self):
        assert extract_numbers("") == []

    def test_no_numbers(self):
        assert extract_numbers("hello world") == []

    def test_currency_symbols(self):
        result = extract_numbers("$40000 car")
        assert 40000.0 in result

    def test_arabic_digits(self):
        result = extract_numbers("عندي ٥٠٠٠")
        assert 5000.0 in result

    def test_deduplication(self):
        result = extract_numbers("5000 5000 5000")
        assert result.count(5000.0) == 1

    def test_numbers_attached_to_arabic_text(self):
        result = extract_numbers("عاوز اشتري عربية 9855وقب شهر 2000")
        assert 9855.0 in result
        assert 2000.0 in result