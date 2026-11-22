"""When a source syncs on its own (K-16-0002 S2-A: fixed choices, no cron string).

`schedule` is one of:
- `{"kind": "manual"}`: only "Sync now", the CLI or the API (the default);
- `{"kind": "hourly", "minute": 0-59}`;
- `{"kind": "daily", "at": "HH:MM"}`;
- `{"kind": "weekly", "weekday": 0-6 (Monday 0), "at": "HH:MM"}`.
Times are UTC (the screen says so). A scheduled run is a raw delta run, then silver and gold for
what changed; a full run (and so a safe delete) is always started explicitly. The sync worker's
minute tick asks `due()` for every active source; a source whose slot passed while the worker was
down runs once at the next tick, never once per missed slot. A source that has never synced is
not scheduled: its first (full) run is started by a person (plan/16: the first full sync runs
uninterrupted before users see the source), so a new source does not start pulling at once.
"""

from datetime import datetime, timedelta

from pydantic import BaseModel, ConfigDict, Field, field_validator

KINDS = ("manual", "hourly", "daily", "weekly")


class Schedule(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: str = "manual"
    minute: int | None = Field(default=None, ge=0, le=59)
    at: str | None = None
    weekday: int | None = Field(default=None, ge=0, le=6)

    @field_validator("kind")
    @classmethod
    def _kind(cls, value: str) -> str:
        if value not in KINDS:
            raise ValueError(f"schedule_invalid: kind must be one of {', '.join(KINDS)}")
        return value

    @field_validator("at")
    @classmethod
    def _at(cls, value: str | None) -> str | None:
        if value is None:
            return value
        hour, sep, minute = value.partition(":")
        if (
            not sep
            or not (hour.isdigit() and minute.isdigit())
            or len(minute) != 2
            or not (0 <= int(hour) <= 23 and 0 <= int(minute) <= 59)
        ):
            raise ValueError("schedule_invalid: at must be HH:MM (UTC)")
        return f"{int(hour):02d}:{minute}"

    def model_post_init(self, _context) -> None:
        needs = {
            "manual": set(),
            "hourly": {"minute"},
            "daily": {"at"},
            "weekly": {"at", "weekday"},
        }[self.kind]
        given = {name for name in ("minute", "at", "weekday") if getattr(self, name) is not None}
        if given != needs:
            raise ValueError(
                f"schedule_invalid: {self.kind} takes {sorted(needs) or 'no fields'}, "
                f"got {sorted(given) or 'none'}"
            )


def last_slot(schedule: Schedule, now: datetime) -> datetime | None:
    """The latest slot at or before `now` (UTC), or None for manual."""
    if schedule.kind == "manual":
        return None
    if schedule.kind == "hourly":
        slot = now.replace(minute=schedule.minute, second=0, microsecond=0)
        return slot if slot <= now else slot - timedelta(hours=1)
    hour, minute = (int(x) for x in schedule.at.split(":"))
    slot = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if schedule.kind == "daily":
        return slot if slot <= now else slot - timedelta(days=1)
    slot -= timedelta(days=(slot.weekday() - schedule.weekday) % 7)
    return slot if slot <= now else slot - timedelta(days=7)


def due(schedule: Schedule, last_started: datetime | None, now: datetime) -> bool:
    """A scheduled run is due when the latest slot passed after the last run started."""
    slot = last_slot(schedule, now)
    if slot is None:
        return False
    return last_started is not None and last_started < slot
