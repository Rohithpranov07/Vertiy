"""Example messages for the Check page.

Each text is the published claim of a real fact-check in the local index (or a plain
message with no fact-check on file), so people can try Verity without hunting for input.
"""

from typing import NamedTuple


class Example(NamedTuple):
    title: str
    kind: str  # what to expect, in words (not a promise: the index can change)
    text: str


EXAMPLES: tuple[Example, ...] = (
    Example(
        "Water and heart attacks",
        "Known false rumour",
        "Japanese method of drinking water on an empty stomach will prevent a heart attack",
    ),
    Example(
        "Cancer cure at home",
        "Known false rumour",
        "Tulsi, lemon and black pepper cure cancer in the snap of a finger",
    ),
    Example(
        "Astronauts without helmets",
        "Misattributed image",
        "Image shows NASA astronauts posing on the moon without helmets",
    ),
    Example(
        "5G and plate tracking",
        "Known false rumour",
        "URGENT: 5G wireless tracking on license plates starting now, share with everyone",
    ),
    Example(
        "Free LPG connections",
        "Supported claim",
        "3.8 crore poor women provided with free LPG connections",
    ),
    Example(
        "Contact details inside",
        "Privacy shield demo",
        "Your bank account is blocked. Call 9876543210 or mail me at ravi@example.com "
        "and verify now",
    ),
    Example(
        "Heavy rain in Chennai",
        "No fact-check on file",
        "Heavy rain expected in Chennai tomorrow, stay safe",
    ),
    Example(
        "Hindi example",
        "Hindi message",
        "रिलायंस जियो ने लॉन्‍च किया जियो 3, 5 जी फोन",
    ),
)
