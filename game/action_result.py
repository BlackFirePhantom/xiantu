"""Stable acknowledgement envelopes shared by Socket.IO game actions."""

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ActionResult:
    ok: bool
    reason: str | None = None
    action_id: str | None = None
    duplicate: bool | None = None
    data: dict = field(default_factory=dict)

    @classmethod
    def success(cls, *, action_id=None, duplicate=None, **data):
        return cls(True, action_id=action_id, duplicate=duplicate, data=data)

    @classmethod
    def failure(cls, reason, *, action_id=None, **data):
        return cls(False, reason=reason, action_id=action_id, data=data)

    def to_dict(self):
        payload = {"ok": self.ok}
        if self.reason is not None:
            payload["reason"] = self.reason
        if self.action_id is not None:
            payload["action_id"] = self.action_id
        if self.duplicate is not None:
            payload["duplicate"] = self.duplicate
        payload.update(self.data)
        return payload
