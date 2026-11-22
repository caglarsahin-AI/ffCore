"""Source permissions to a document's ACL (C15), the safe side by default.

A source reports group names and member e-mails for an item (`SourceAcl`). `acl_mappings` maps a
group to one platform role or one platform user; the platform has no group entity, so a group
is expanded into roles and user ids at sync time and written to `documents.acl_roles` /
`acl_users`; a membership change reaches the index on the next sync.

Rules (plan/16 "ACL eşleme"):
- a group without a mapping row gives nothing but the admin default: an item none of whose
  groups is mapped (or that names no group at all) is readable by admins only. A source never
  opens a document silently; opening is a mapping row someone wrote (`*` maps every item).
- a mapped role is that role (C15 then lets every role above it read, as for uploads);
- a member e-mail is matched to a platform user by e-mail (the channel rule, ARCH-10); an
  address without a user is counted (`unmatched`), never guessed, and gives no access.
- network folders report their folder chain as groups `folder:/`, `folder:/a`, `folder:/a/b`
  and resolve with `most_specific=True`: only the deepest mapped folder counts, so a row
  `folder:/sozlesmeler/yonetim` → admin narrows that subtree even when `folder:/` → analyst
  (a union would let analysts read it). Confluence/Jira groups are a union: each one the source
  lists may read the item.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

ADMIN_ONLY = ("admin",)
EVERY_ITEM = "*"


@dataclass(frozen=True)
class AclRule:
    external_group: str
    role: str | None = None
    user_id: str | None = None


@dataclass(frozen=True)
class ResolvedAcl:
    roles: tuple[str, ...]
    users: tuple[str, ...]
    unmapped_groups: tuple[str, ...] = ()
    unmatched_emails: int = 0
    default_admin: bool = False
    detail: dict = field(default_factory=dict)

    def as_acl(self) -> dict:
        return {"roles": list(self.roles), "users": list(self.users)}


def folder_groups(relpath: str) -> tuple[str, ...]:
    """`a/b/c.md` → (`folder:/`, `folder:/a`, `folder:/a/b`)."""
    parts = [p for p in relpath.split("/")[:-1] if p]
    groups = ["folder:/"]
    for n in range(1, len(parts) + 1):
        groups.append("folder:/" + "/".join(parts[:n]))
    return tuple(groups)


def resolve(
    groups: Iterable[str],
    user_emails: Iterable[str],
    mappings: Iterable[AclRule],
    users_by_email: Mapping[str, str],
    *,
    most_specific: bool = False,
) -> ResolvedAcl:
    groups = tuple(dict.fromkeys(g for g in groups if g))
    by_group: dict[str, list[AclRule]] = {}
    for row in mappings:
        by_group.setdefault(row.external_group, []).append(row)
    roles: list[str] = []
    users: list[str] = []
    unmapped = tuple(g for g in groups if g not in by_group)
    mapped = [g for g in groups if g in by_group]
    if most_specific and mapped:
        mapped = mapped[-1:]  # groups come general → specific
    if not mapped and EVERY_ITEM in by_group:
        mapped = [EVERY_ITEM]
    elif not most_specific and EVERY_ITEM in by_group:
        mapped.append(EVERY_ITEM)
    for group in mapped:
        for row in by_group[group]:
            if row.role is not None:
                roles.append(row.role)
            if row.user_id is not None:
                users.append(str(row.user_id))
    unmatched = 0
    for email in dict.fromkeys(e.strip().lower() for e in user_emails if e and e.strip()):
        user = users_by_email.get(email)
        if user is None:
            unmatched += 1
        else:
            users.append(str(user))
    roles = list(dict.fromkeys(roles))
    users = list(dict.fromkeys(users))
    default_admin = not roles and not users
    if default_admin:
        roles = list(ADMIN_ONLY)
    return ResolvedAcl(
        roles=tuple(roles),
        users=tuple(users),
        unmapped_groups=unmapped,
        unmatched_emails=unmatched,
        default_admin=default_admin,
    )
