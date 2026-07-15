"""Validation helpers for untrusted Socket.IO event payloads."""


def get_choice_index(payload, option_count):
    """Return a valid non-negative choice index, or ``None`` for invalid input."""
    if not isinstance(payload, dict) or not isinstance(option_count, int) or option_count <= 0:
        return None

    choice_index = payload.get("choice", 0)
    if type(choice_index) is not int or not 0 <= choice_index < option_count:
        return None
    return choice_index


def get_fortune_choice(payload, events):
    """Return a validated ``(event, choice_index)`` pair for a fortune event."""
    if not isinstance(payload, dict):
        return None

    event_id = payload.get("event_id")
    if not isinstance(event_id, str):
        return None

    event = next((candidate for candidate in events if candidate["id"] == event_id), None)
    if not event:
        return None

    choice_index = get_choice_index(payload, len(event["choices"]))
    if choice_index is None:
        return None
    return event, choice_index
