from app.quotes import locate_quote


def test_offsets_count_code_points_not_utf16_units():
    # The emoji is one code point but two UTF-16 units: JavaScript's indexOf would say 4.
    text = "🙂 € Invoices are payable within 60 days."
    start, end = locate_quote(text, "Invoices")
    assert (start, end) == (4, 12)
    assert text[start:end] == "Invoices"


def test_first_exact_occurrence_wins():
    assert locate_quote("fee, fee", "fee") == (0, 3)


def test_quote_not_in_text_has_no_offsets():
    assert locate_quote("Payment within 30 days.", "Payment within 60 days.") == (None, None)
