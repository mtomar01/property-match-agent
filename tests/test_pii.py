import pytest

from core import pii


@pytest.mark.parametrize(
    "text",
    [
        "Καλέστε 6971234567 για ραντεβού",
        "τηλ. 210 123 4567",
        "Τηλ επικοινωνίας: 697 123 4567",
        "REAL ENERGY HOUSE ΤΗΛ.697674836",  # 9 digits, a real truncated case
        "+30 210 5551234",
        "στείλτε email στο agent@example.gr",
    ],
)
def test_finds_and_scrubs_contact_details(text):
    assert pii.find_pii(text)
    cleaned = pii.scrub(text)
    assert not pii.find_pii(cleaned)
    assert "removed]" in cleaned


@pytest.mark.parametrize(
    "text",
    [
        "€1.050.000",
        "σε οικόπεδο 1.400 τ.μ.",
        "Έχει κατασκευαστεί το 1969 και ανακαινίστηκε το 2026",
        "Κωδικός ακινήτου: 47-4557",
        "τιμή εκκίνησης 124.100 ευρώ",
        "Ανανεώθηκε: 20/10/2026",
        "με θυροτηλεόραση και συναγερμό",
    ],
)
def test_leaves_ordinary_numbers_alone(text):
    assert pii.find_pii(text) == []
    assert pii.scrub(text) == text


def test_scrub_is_idempotent():
    once = pii.scrub("τηλ 6971234567")
    assert pii.scrub(once) == once
