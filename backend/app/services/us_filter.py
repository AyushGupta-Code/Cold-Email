from __future__ import annotations

import re

STATE_ABBREVIATIONS = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DC", "DE", "FL", "GA", "HI", "IA", "ID", "IL", "IN", "KS",
    "KY", "LA", "MA", "MD", "ME", "MI", "MN", "MO", "MS", "MT", "NC", "ND", "NE", "NH", "NJ", "NM", "NV",
    "NY", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VA", "VT", "WA", "WI", "WV", "WY",
}

STATE_NAMES = {
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado", "connecticut", "delaware",
    "district of columbia", "florida", "georgia", "hawaii", "idaho", "illinois", "indiana", "iowa",
    "kansas", "kentucky", "louisiana", "maine", "maryland", "massachusetts", "michigan", "minnesota",
    "mississippi", "missouri", "montana", "nebraska", "nevada", "new hampshire", "new jersey", "new mexico",
    "new york", "north carolina", "north dakota", "ohio", "oklahoma", "oregon", "pennsylvania", "rhode island",
    "south carolina", "south dakota", "tennessee", "texas", "utah", "vermont", "virginia", "washington",
    "west virginia", "wisconsin", "wyoming",
}

MAJOR_US_METROS = {
    "austin", "seattle", "new york", "san francisco", "boston", "los angeles", "chicago", "atlanta",
    "dallas", "houston", "miami", "denver", "philadelphia", "phoenix", "san diego", "bay area",
    "washington dc", "dc-baltimore", "silicon valley",
}

NON_US_HINTS = {
    "canada", "toronto", "vancouver", "london", "united kingdom", "uk", "india", "germany", "berlin",
    "france", "singapore", "australia", "ireland", "spain", "poland", "brazil", "mexico",
}


def assess_us_location(text: str) -> tuple[bool, float, list[str]]:
    value = (text or "").strip()
    lowered = value.lower()
    evidence: list[str] = []
    confidence = 0.0

    if re.search(r"\bunited states\b", lowered):
        evidence.append("mentions United States")
        confidence = max(confidence, 0.98)
    if re.search(r"\bu\.?s\.?a?\b", lowered):
        evidence.append("mentions US/USA")
        confidence = max(confidence, 0.9)
    if re.search(r"\bremote\b", lowered) and re.search(r"\b(united states|u\.?s\.?a?)\b", lowered):
        evidence.append("mentions remote US")
        confidence = max(confidence, 0.96)

    city_state_match = re.search(r"\b([A-Z][A-Za-z.\- ]+),\s*([A-Z]{2})\b", value)
    if city_state_match and city_state_match.group(2) in STATE_ABBREVIATIONS:
        evidence.append(f"matches city/state pattern: {city_state_match.group(0)}")
        confidence = max(confidence, 0.92)

    for state_name in STATE_NAMES:
        if re.search(rf"\b{re.escape(state_name)}\b", lowered):
            evidence.append(f"mentions state name: {state_name.title()}")
            confidence = max(confidence, 0.82)
            break

    for metro in MAJOR_US_METROS:
        if re.search(rf"\b(?:greater\s+)?{re.escape(metro)}(?:\s+city)?(?:\s+metropolitan area|\s+area)\b", lowered):
            evidence.append(f"matches metro-area pattern: {metro.title()}")
            confidence = max(confidence, 0.84)
            break
        if re.search(rf"\b{re.escape(metro)}\b", lowered):
            evidence.append(f"mentions US metro: {metro.title()}")
            confidence = max(confidence, 0.76)
            break

    non_us_found = [hint for hint in NON_US_HINTS if re.search(rf"\b{re.escape(hint)}\b", lowered)]
    if non_us_found and confidence < 0.9:
        confidence = max(confidence - 0.25, 0.0)
        evidence.append(f"contains non-US hint: {non_us_found[0]}")

    return confidence >= 0.7, round(confidence, 3), evidence


def is_us_based(text: str, min_confidence: float = 0.7) -> bool:
    matched, confidence, _ = assess_us_location(text)
    return matched and confidence >= min_confidence
