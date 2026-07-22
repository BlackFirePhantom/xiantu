from game.action_result import ActionResult


def test_action_result_builds_stable_success_envelope():
    result = ActionResult.success(action_id="realm-action-001", duplicate=True)

    assert result.to_dict() == {
        "ok": True,
        "action_id": "realm-action-001",
        "duplicate": True,
    }


def test_action_result_builds_stable_error_envelope_without_empty_fields():
    result = ActionResult.failure("invalid_action")

    assert result.to_dict() == {"ok": False, "reason": "invalid_action"}
