"""Approval queue rules (07) shared by the routes, the TTL job and the run hook."""

from ffcore.core.auth import ROLE_ORDER, Actor, Grant


def tool_key(action: str) -> str | None:
    """`<tool_key>__<action>` (C7) -> `<tool_key>`; None for a name without the separator."""
    key, sep, _ = action.partition("__")
    return key if sep and key else None


def may_decide(actor: Actor, grant: Grant | None, assigned_role: str) -> bool:
    """Approve or reject needs a person in a console session (K-07-0002 B3): never a service
    account, an API key, or a user reached through X-On-Behalf-Of; `edit` access and a role at
    least `assigned_role`."""
    if actor.actor_type != "user" or actor.via_service or grant is None:
        return False
    if grant.access != "edit":
        return False
    return ROLE_ORDER.index(grant.role) >= ROLE_ORDER.index(assigned_role)
