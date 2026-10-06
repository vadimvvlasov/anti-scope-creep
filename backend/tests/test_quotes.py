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


# Quote verification for the LLM analyzer: the model may change typography when it quotes.


def test_curly_quotes_in_the_text_match_straight_quotes_in_the_quote():
    text = "The “Deliverables” include the Client’s logo."
    start, end = locate_quote(text, 'The "Deliverables" include the Client\'s logo.')
    assert (start, end) == (0, len(text))


def test_dashes_match_a_hyphen():
    text = "Payment terms — Net 90 – from acceptance."
    start, end = locate_quote(text, "Payment terms - Net 90 - from acceptance.")
    assert text[start:end] == text


def test_line_breaks_and_repeated_spaces_inside_the_quote():
    text = "Intro.\nThe Client may request\n  revisions at any time.\nEnd."
    start, end = locate_quote(text, "The Client may request revisions at any time.")
    assert text[start:end] == "The Client may request\n  revisions at any time."


def test_offsets_point_into_the_original_text_after_an_emoji():
    text = "\U0001f642  Invoices are payable\nwithin 60 days."
    start, end = locate_quote(text, "Invoices are payable within 60 days.")
    assert (start, end) == (3, len(text))


def test_quote_at_the_very_start_and_end_of_the_text():
    text = "“Fee” — net 30"
    assert locate_quote(text, '"Fee" - net 30') == (0, len(text))


def test_surrounding_whitespace_in_the_quote_is_ignored():
    text = "A. The fee is fixed. B."
    start, end = locate_quote(text, "  The fee\nis fixed.  ")
    assert text[start:end] == "The fee is fixed."


def test_exact_occurrence_wins_over_an_earlier_normalized_one():
    text = "fee — due; fee - due"
    assert locate_quote(text, "fee - due") == (11, 20)


def test_other_differences_still_do_not_match():
    assert locate_quote("Payment within 30 days.", "payment within 30 days.") == (None, None)
    assert locate_quote("Payment within 30 days.", "Payment within 30 days") == (0, 22)
    assert locate_quote("Payment within 30 days.", "Payment, within 30 days.") == (None, None)


def test_a_quote_that_is_empty_after_normalization_has_no_offsets():
    assert locate_quote("Some text.", "") == (None, None)
    assert locate_quote("Some  text.", "  \n ") == (None, None)
