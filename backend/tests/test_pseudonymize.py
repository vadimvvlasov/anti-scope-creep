import logging
import re
from pathlib import Path

import pytest

from app.pseudonymize import PlaceholderMap, pseudonymize, restore
from tests.samples import ENGLISH_CONTRACT

CONTRACT = """SERVICES AGREEMENT

This Agreement is entered into on March 3, 2026 between Northwind Traders Inc., a Delaware corporation ("Client"), and Jane Doe ("Contractor").

1. Fees. Client shall pay USD 12,500 in two milestones. Invoices are payable within 60 days (Net 60).
2. Liability. Contractor's liability is capped at 100% of the fees paid in the last 12 months.
3. Notices. Notices to Northwind Traders Inc. go to legal@northwind.example, phone +1 (555) 010-7788;
   notices to Jane Doe go to jane.doe@mail.example, Tel: 020 7946 0958, https://janedoe.example/portfolio.
4. Payment details. IBAN: DE89 3704 0044 0532 0130 00. Account number: 000123456789.
   Contractor tax ID: 12-3456789. Company registration number: HRB 98765.
5. Term. This Agreement starts on 2026-04-01 and lasts 6 months; either party may terminate with 30 days notice.

Northwind Traders Inc.
By: Robert Miles, CEO

Contractor
Name: Jane Doe
"""

SECRETS = (
    "Northwind Traders Inc.", "Jane Doe", "Robert Miles", "legal@northwind.example",
    "jane.doe@mail.example", "+1 (555) 010-7788", "020 7946 0958", "https://janedoe.example/portfolio",
    "DE89 3704 0044 0532 0130 00", "000123456789", "12-3456789", "HRB 98765",
)
KEPT = (
    "March 3, 2026", "USD 12,500", "60 days", "Net 60", "100%", "12 months", "2026-04-01",
    "6 months", "30 days", "Delaware",
)


def test_parties_signatories_and_contacts_are_replaced():
    text, mapping = pseudonymize(CONTRACT)

    for secret in SECRETS:
        assert secret not in text, secret
    assert 'between [PARTY_A], a Delaware corporation ("Client"), and [PARTY_B] ("Contractor")' in text
    assert "By: [PERSON_1], CEO" in text
    assert "Name: [PARTY_B]" in text  # the freelancer signs as a party, not a new person
    assert "[EMAIL_1]" in text and "[EMAIL_2]" in text
    assert "IBAN: [IBAN_1]" in text and "Account number: [ACCOUNT_1]" in text
    assert "tax ID: [ID_1]" in text and "registration number: [ID_2]" in text
    assert "[PHONE_1]" in text and "Tel: [PHONE_2]" in text
    assert "[URL_1]" in text
    assert len(mapping) == 12


def test_amounts_periods_dates_and_percentages_stay():
    text, _ = pseudonymize(CONTRACT)
    for value in KEPT:
        assert value in text, value


def test_the_same_value_gets_the_same_placeholder_everywhere():
    text, _ = pseudonymize(CONTRACT)
    assert text.count("[PARTY_A]") == 3  # preamble, notices, signature block
    assert text.count("[PARTY_B]") == 3


def test_role_words_alone_are_not_names():
    text, mapping = pseudonymize("This Agreement is between the Client and the Contractor.\nBy: Client\n")
    assert len(mapping) == 0
    assert text == "This Agreement is between the Client and the Contractor.\nBy: Client\n"


def test_restore_round_trip():
    text, mapping = pseudonymize(CONTRACT)
    restored, unknown = restore(text, mapping)
    assert restored == CONTRACT
    assert unknown == []


def test_restore_reports_unknown_and_unbracketed_placeholders():
    _, mapping = pseudonymize(CONTRACT)
    restored, unknown = restore("[PARTY_A] pays [PARTY_C]; PARTY_B signs.", mapping)
    assert restored.startswith("Northwind Traders Inc. pays [PARTY_C]")
    assert unknown == ["[PARTY_C]", "PARTY_B"]


def test_the_mapping_does_not_show_original_values(caplog):
    caplog.set_level(logging.DEBUG)
    text, mapping = pseudonymize(CONTRACT)
    restore(text, mapping)
    shown = repr(mapping) + str(mapping) + caplog.text
    for secret in SECRETS:
        assert secret not in shown, secret


def test_one_mapping_per_call():
    _, first = pseudonymize("Notices go to a@example.com.")
    text, second = pseudonymize("Notices go to b@example.com.")
    assert text == "Notices go to [EMAIL_1]."
    assert first is not second and isinstance(second, PlaceholderMap)


def test_the_sample_contract_has_nothing_to_hide():
    assert pseudonymize(ENGLISH_CONTRACT) == (ENGLISH_CONTRACT, PlaceholderMap())


def test_text_without_personal_data_is_unchanged():
    text, mapping = pseudonymize("Payment is due within 30 days of the invoice date, 2026-05-01.")
    assert text == "Payment is due within 30 days of the invoice date, 2026-05-01."
    assert len(mapping) == 0


def test_an_address_between_the_name_and_the_role_is_not_a_party():
    # From a real-world layout: a long address sits between the company and ("Client").
    text, mapping = pseudonymize(
        'by and between Apex Logistics Inc., a Delaware corporation with its principal place of '
        'business at 100 Montgomery Street, Suite 1800, San Francisco, CA 94104 ("Client"), and '
        'DevPulse LLC, a Texas limited liability company ("Developer").'
    )
    assert text.startswith("by and between [PARTY_A], a Delaware corporation")
    assert 'principal place of business at [ADDRESS_1] ("Client")' in text
    assert "and [PARTY_B], a Texas limited liability company" in text
    assert len(mapping) == 3  # two parties and the address, which is not a party


def test_numbered_party_list_ids_and_passports():
    text, _ = pseudonymize(
        "PARTIES TO THIS AGREEMENT:\n\n"
        "1. Borealis Cloud Services Sp. z o.o., a corporation organized under the laws of Poland "
        "(Corporate Registration No: PL-KRS-0000123456, Tax ID/VAT: PL5213456789), represented by "
        "its authorized signatory, Anna Nowak (Personal Identification No: ID/Passport N-9876543), "
        'hereinafter referred to as "Party A" or "Client";\n\n'
        "2. Helvetia Data AG, a commercial enterprise (Corporate Registration No: CH-CHE-123.456.789), "
        'hereinafter "Party B" or "Contractor".\n\n'
        "Client registration/reference ID: REG-2026-10004.\n"
        "Project reference: REG-2026-10004\n"
        "Effective on 2026-05-13 with registration completed on 2026-05-20.\n\n"
        "Name: Anna Nowak\n"
    )
    for secret in (
        "Borealis", "Helvetia", "Anna Nowak", "PL-KRS-0000123456", "PL5213456789", "N-9876543",
        "CH-CHE-123.456.789", "REG-2026-10004",
    ):
        assert secret not in text, secret
    assert text.startswith("PARTIES TO THIS AGREEMENT:\n\n1. [PARTY_A], a corporation organized")
    assert "Project reference: [ID_" in text  # an ID found once is hidden where it repeats
    assert "2026-05-13" in text and "2026-05-20" in text


def test_labelled_addresses_are_replaced():
    text, _ = pseudonymize(
        'Jane Doe, an individual residing at 12 Rose Lane, Bristol BS1 4DJ ("Contractor").\n'
        "Address: Taunusanlage 8, 60329 Frankfurt am Main, Germany\n"
        "The Client is located at 25 Bank Street, London E14 5JP. Payment within 30 days.\n"
        "Documents are located at https://example.com/portal; the address of the courts applies.\n"
    )
    for secret in ("12 Rose Lane", "Bristol BS1 4DJ", "Taunusanlage 8", "60329", "25 Bank Street", "E14 5JP"):
        assert secret not in text, secret
    assert 'Jane Doe' not in text and 'residing at [ADDRESS_1] ("Contractor")' in text
    assert "Address: [ADDRESS_2]\n" in text
    assert "located at [ADDRESS_3]. Payment within 30 days." in text
    assert "located at [URL_1]; the address of the courts applies." in text  # no digit, no address


# Synthetic test contracts (not real data) in data/ at the repository root.
FIXTURES = sorted((Path(__file__).resolve().parents[2] / "data").glob("*.txt"))
LEFTOVERS = {
    "email": r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+",
    "url": r"\b(?:https?://|www\.)\S+",
    "phone": r"\+\d[\d ().-]{6,}\d",
    "iban": r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){2,}",
    "street": r"\b\d+[A-Za-z]* [A-Z][a-z]+ (?:Street|Avenue|Boulevard|Plaza|Road|Square|Way|Drive|Lane)\b",
}
KEEP = r"(?:USD|EUR|GBP|\$|€|£)\s?[\d,]+(?:\.\d+)?|\d+(?:\.\d+)?%|\b\d{4}-\d{2}-\d{2}\b|\b\d+ (?:days|months|years)\b"


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.name)
def test_fixture_contracts(path):
    source = path.read_text(encoding="utf-8")
    text, mapping = pseudonymize(source)

    for kind, pattern in LEFTOVERS.items():
        assert not re.findall(pattern, text), kind
    for value in re.findall(KEEP, source):
        assert value in text, value
    assert restore(text, mapping) == (source, [])
    assert len(mapping) > 0
