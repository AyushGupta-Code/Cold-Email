from app.services.us_filter import assess_us_location, is_us_based


def test_detects_city_state_pattern() -> None:
    matched, confidence, evidence = assess_us_location("Austin, TX")
    assert matched is True
    assert confidence >= 0.9
    assert evidence


def test_detects_united_states_phrase() -> None:
    assert is_us_based("Remote - United States") is True


def test_detects_linkedin_metro_area_pattern() -> None:
    matched, confidence, evidence = assess_us_location("Greater Seattle Area")
    assert matched is True
    assert confidence >= 0.8
    assert evidence


def test_rejects_non_us_location() -> None:
    matched, confidence, _ = assess_us_location("Toronto, Canada")
    assert matched is False
    assert confidence < 0.7


def test_does_not_misread_regular_word_as_us() -> None:
    matched, _, _ = assess_us_location("Focus on distributed systems")
    assert matched is False
