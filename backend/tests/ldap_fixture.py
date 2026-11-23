"""17: a synthetic directory on an ldap3 MOCK_SYNC server (in process, no network).

`FakeDirectory` loads tests/fixtures/ldap/directory.json; tests remove users, change groups,
disable accounts, break the service account or make the directory unreachable. objectGUID is
stored as Active Directory sends it (16 little-endian bytes). Each instance gives its users a
fresh suffix (account name, email, GUID): the integration database is shared by all tests.
"""

import json
import uuid
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "ldap" / "directory.json"
HOST = "dir.example.test"

DATA = json.loads(FIXTURE.read_text(encoding="utf-8"))
BASE = DATA["base"]
SERVICE_DN = DATA["service"]["dn"]
SERVICE_PASSWORD = DATA["service"]["password"]
GROUPS = DATA["groups"]
USERS = {u["sAMAccountName"]: u for u in DATA["users"]}


def ldap_settings(settings, **changes):
    """`settings` with the fake directory configured (validated like a real start-up)."""
    from ffcore.core.config import Settings

    values = settings.model_dump()
    values.update(
        ldap_url=f"ldaps://{HOST}",
        ldap_bind_dn=SERVICE_DN,
        ldap_bind_password=SERVICE_PASSWORD,
        ldap_user_base=BASE,
        allowed_internal_hosts=[*settings.allowed_internal_hosts, HOST, "127.0.0.1"],
    )
    values.update(changes)
    for name, value in list(values.items()):
        if hasattr(value, "get_secret_value"):
            values[name] = value.get_secret_value()
    return Settings(**values)


class FakeDirectory:
    def __init__(self) -> None:
        from ldap3 import MOCK_SYNC, Connection, Server

        tag = uuid.uuid4().hex[:8]
        # Group DNs are unique per instance too: mappings live in the shared database.
        self.groups = {key: dn.replace(",OU=", f"-{tag},OU=", 1) for key, dn in GROUPS.items()}
        self.users: dict[str, dict] = {}
        for name, user in USERS.items():
            unique = dict(user)
            unique["dn"] = user["dn"].replace(f"cn={name},", f"cn={name}-{tag},")
            unique["sAMAccountName"] = f"{name}-{tag}"
            for attr in ("mail", "userPrincipalName"):
                if user.get(attr):
                    unique[attr] = user[attr].replace("@", f"-{tag}@")
            unique["objectGUID"] = str(uuid.uuid4())
            self.users[name] = unique

        self._mock = MOCK_SYNC
        self.server = Server(HOST)
        self.unreachable = False
        self._seed = Connection(
            self.server, user=SERVICE_DN, password=SERVICE_PASSWORD, client_strategy=MOCK_SYNC
        )
        self._seed.strategy.add_entry(
            SERVICE_DN, {"userPassword": SERVICE_PASSWORD, "objectClass": "person"}
        )
        self.entries: dict[str, dict] = {}
        for name, user in self.users.items():
            self.put(name, dict(user))

    def put(self, name: str, user: dict) -> None:
        if name in self.entries:
            self._seed.strategy.remove_entry(self.entries[name]["dn"])
        attributes = {
            "userPassword": user["password"],
            "objectClass": "person",
            "sAMAccountName": user["sAMAccountName"],
            "displayName": user["displayName"],
            "objectGUID": uuid.UUID(user["objectGUID"]).bytes_le,
            "memberOf": [self.groups[g] for g in user["memberOf"]],
            "userAccountControl": user["userAccountControl"],
        }
        for optional in ("mail", "userPrincipalName"):
            if user.get(optional):
                attributes[optional] = user[optional]
        self._seed.strategy.add_entry(user["dn"], attributes)
        self.entries[name] = user

    def remove(self, name: str) -> None:
        self._seed.strategy.remove_entry(self.entries.pop(name)["dn"])

    def set_groups(self, name: str, groups: list[str]) -> None:
        self.put(name, {**self.entries[name], "memberOf": groups})

    def disable(self, name: str) -> None:
        self.put(name, {**self.entries[name], "userAccountControl": 514})

    def endpoint(self, settings):
        from ldap3 import SYNC, Server

        from ffcore.core.ldap_auth import LdapEndpoint

        if self.unreachable:
            # A real socket that refuses: the driver must answer 503, never fall back.
            return LdapEndpoint(Server("127.0.0.1", port=1, connect_timeout=1), SYNC)
        return LdapEndpoint(self.server, self._mock)

    def directory(self, settings):
        from ffcore.core.ldap_auth import LdapDirectory

        return LdapDirectory(settings, self.endpoint)

    def login(self, name: str) -> str:
        return self.users[name]["sAMAccountName"]

    def email(self, name: str) -> str:
        return self.users[name].get("mail") or ""

    def guid(self, name: str) -> str:
        return self.users[name]["objectGUID"]

    def password(self, name: str) -> str:
        return self.users[name]["password"]

    def group(self, key: str) -> str:
        """The DN as the directory sends it (mixed case)."""
        return self.groups[key]
