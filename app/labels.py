"""Human-readable names for enum values, shared by the web pages and the description writer."""

_SPECIAL = {"suv": "SUV", "gps": "GPS"}


def label(value: object) -> str:
    """`air_conditioning` -> `Air conditioning`, `suv` -> `SUV`."""
    text = str(value)
    if text in _SPECIAL:
        return _SPECIAL[text]
    return text.replace("_", " ").capitalize()


def lower_label(value: object) -> str:
    """Same as label but lower case inside a sentence, keeping acronyms: `SUV`, `air conditioning`."""
    text = label(value)
    return text if str(value) in _SPECIAL else text.lower()
