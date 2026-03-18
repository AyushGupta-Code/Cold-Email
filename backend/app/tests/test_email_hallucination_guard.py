from app.services.contact_discovery import extract_verified_public_email


def test_extracts_only_literal_public_email() -> None:
    value = extract_verified_public_email("Reach me at jane.doe@example.com")
    assert value == "jane.doe@example.com"


def test_does_not_guess_missing_email() -> None:
    value = extract_verified_public_email("Jane Doe works at Example Corp in Austin, TX")
    assert value is None

