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


# The model may shorten a clause with an ellipsis or drop a word; the stored quote is
# then the contract's own slice. Words that could change the meaning must still match.

_M7 = (
    "2.1 Total Fixed Price. Client agrees to pay Developer a total fixed price of $85,000.00 USD. "
    "Client shall pay each milestone amount within ninety (90) days after Client's final acceptance "
    "of the complete Software.\n2.2 Expenses. None."
)


def test_a_dropped_word_matches_the_contract_clause():
    start, end = locate_quote(
        _M7, "Client shall pay each milestone within ninety (90) days after Client's final acceptance of the complete Software."
    )
    assert _M7[start:end] == (
        "Client shall pay each milestone amount within ninety (90) days after Client's final acceptance of the complete Software"
    )


def test_a_changed_number_does_not_match():
    quote = "Client shall pay each milestone amount within thirty (30) days after Client's final acceptance of the complete Software."
    assert locate_quote(_M7, quote) == (None, None)


def test_a_changed_meaning_word_does_not_match():
    text = "The parties intend to allow 3 rounds of ordinary revisions for the principal creative deliverables."
    quote = "The parties intend to allow unlimited rounds of ordinary revisions for the principal creative deliverables."
    assert locate_quote(text, quote) == (None, None)
    negated = "The Contractor shall be liable for indirect damages arising out of the Services under this Agreement."
    assert locate_quote(negated.replace("shall be", "shall not be"), negated) == (None, None)


def test_a_short_quote_is_not_matched_by_words():
    assert locate_quote("The fee is payable on delivery.", "The fee is payable upon delivery.") == (None, None)


def test_an_ellipsis_spans_from_the_first_part_to_the_last():
    text = (
        "9. Termination. Customer may terminate this Agreement for convenience at the end of any month, "
        "provided that Customer gives Provider at least ten days notice. Other text."
    )
    quote = "Customer may terminate this Agreement ... gives Provider at least ten days notice."
    start, end = locate_quote(text, quote)
    assert text[start:end] == (
        "Customer may terminate this Agreement for convenience at the end of any month, "
        "provided that Customer gives Provider at least ten days notice."
    )
    assert locate_quote(text, quote.replace(" ... ", "… ")) == (start, end)


def test_ellipsis_parts_out_of_order_or_too_short_do_not_match():
    text = "Customer may terminate this Agreement at any time. Provider shall deliver all source code monthly."
    assert locate_quote(text, "Provider shall deliver all source ... Customer may terminate this Agreement") == (None, None)
    assert locate_quote(text, "Customer may ... source code monthly.") == (None, None)


def test_ellipsis_parts_far_apart_do_not_match():
    text = "Customer may terminate this Agreement now. " + "Filler sentence here. " * 400 + "Provider keeps all rights forever."
    assert locate_quote(text, "Customer may terminate this Agreement ... Provider keeps all rights forever.") == (None, None)


def test_a_replaced_or_added_word_does_not_match():
    text = (
        "Any post-launch support period is limited to the duration and scope stated in the commercial schedule. "
        "Requests outside that scope are handled as new Services or change requests."
    )
    quote = (
        "Any post-launch support period is limited to the duration and scope stated in the commercial schedule. "
        "Requests outside that scope are handled as part of the Services."
    )
    assert locate_quote(text, quote) == (None, None)
    assert locate_quote(_M7, "Client shall promptly pay each milestone amount within ninety (90) days.") == (None, None)


def test_more_than_two_omitted_words_do_not_match():
    quote = "Client shall pay each milestone within days after Client's final acceptance of the Software."
    assert locate_quote(_M7.replace("ninety (90) ", "the agreed "), quote) == (None, None)
