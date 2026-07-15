import pytest
from pathlib import Path

from config import parse_cors_origins
from handlers.security import get_choice_index, get_fortune_choice


@pytest.mark.parametrize(
    ("payload", "option_count"),
    [
        ({"choice": -1}, 3),
        ({"choice": 3}, 3),
        ({"choice": "1"}, 3),
        ({"choice": True}, 3),
        (None, 3),
    ],
)
def test_get_choice_index_rejects_invalid_socket_payloads(payload, option_count):
    assert get_choice_index(payload, option_count) is None


def test_get_choice_index_uses_zero_as_the_default_choice():
    assert get_choice_index({}, 3) == 0


def test_get_choice_index_returns_a_valid_explicit_choice():
    assert get_choice_index({"choice": 2}, 3) == 2


@pytest.mark.parametrize("payload", [None, "not-a-payload", {"event_id": 42}, {"event_id": "missing"}])
def test_get_fortune_choice_rejects_invalid_payloads(payload):
    events = [{"id": "mountain", "choices": [{}, {}]}]

    assert get_fortune_choice(payload, events) is None


def test_get_fortune_choice_returns_the_selected_event_and_index():
    event = {"id": "mountain", "choices": [{}, {}]}

    assert get_fortune_choice({"event_id": "mountain", "choice": 1}, [event]) == (event, 1)


def test_parse_cors_origins_defaults_to_same_origin_only():
    assert parse_cors_origins("") is None
    assert parse_cors_origins(None) is None


def test_parse_cors_origins_normalizes_a_comma_separated_allowlist():
    assert parse_cors_origins(" https://game.example.com, https://admin.example.com ") == [
        "https://game.example.com",
        "https://admin.example.com",
    ]


def test_auth_forms_expose_labeled_autocomplete_fields():
    template = Path("templates/index.html").read_text(encoding="utf-8")

    assert 'label for="login-username"' in template
    assert 'id="login-username" type="text" name="username" autocomplete="username"' in template
    assert 'id="login-password" type="password" name="password" autocomplete="current-password"' in template
    assert 'id="register-password" type="password" name="password" autocomplete="new-password"' in template
