# Directory sign-in (package 17)

FFCore opens to the organisation's users through its own directory: people sign in with their
Active Directory / LDAP account, their platform account is created at the first sign-in, and the
directory's groups decide which projects they see and with which role. Nobody opens accounts by
hand, and an account the directory disables stops working the next day.

This page covers LDAP / Active Directory (17-1). Sign-in with an OIDC identity provider
(Keycloak, Entra ID) follows in 17-2; the widget's token exchange for channels is package 15's
(it uses the same resolver, "Channels" below).

## What changes for whom

| Who | Before | With a directory |
|---|---|---|
| End user | no account | signs in with the directory account on the same login form (email, UPN or account name); sees only the chat, their own memory and channels |
| Project admin | adds members one by one | maps a directory group to a project role; members follow the group |
| Superadmin | opens every account | keeps a **local** account (the recovery account); sees provider status, tests the connection, imports local exceptions |

The `user` role (end user) is assignable from 17 on: a `user` member reaches the chat (published agents, conversations,
their own runs) and `/memories`; every console route answers 403
`insufficient_role`. `developer` stays reserved.

## Settings (`.env`)

The directory is configured in `.env` (it holds the service account's password); group mappings
live in the database and are edited on screen.

| Setting | Meaning |
|---|---|
| `LDAP_URL` | `ldaps://dc.example.com:636`. Empty: directory sign-in is off. `ldap://` is refused unless `LDAP_ALLOW_PLAINTEXT=true` (a test directory only; preflight warns) |
| `LDAP_BIND_DN`, `LDAP_BIND_PASSWORD` | a read-only service account that searches users |
| `LDAP_USER_BASE` | where users are searched, e.g. `OU=People,DC=example,DC=com` |
| `LDAP_USER_FILTER` | default `(\|(mail={login})(userPrincipalName={login})(sAMAccountName={login}))`; `{login}` is the escaped value the user typed |
| `LDAP_GROUP_ATTR` | `memberOf` |
| `LDAP_ID_ATTR` | the stable account id: `objectGUID` (Active Directory) or `entryUUID` (OpenLDAP). Chosen explicitly; never guessed |
| `LDAP_CA_FILE` | the corporate CA bundle for `ldaps`, a path **inside the backend container** (below). Empty: the system trust store |
| `LDAP_TIMEOUT_S` | seconds for the connection and for each answer (default 10) |
| `LOCAL_LOGIN` | `all` (default), `superadmin_only` or `off` (below) |
| `DEFAULT_PROJECT_FOR_NEW_USERS` | a project key every directory account joins as `user`/`read`; empty: none (the safe side) |
| `AUTO_PROVISION_FROM_CHANNELS` | `false` (default): a channel user without an account is refused politely (15) |
| `OIDC_INACTIVE_AFTER_DAYS` | OIDC accounts unused this long are deactivated (90) |

The directory host must be reachable under the egress rules like any other destination: in
`airgap` and for an internal directory add it to `ALLOWED_INTERNAL_HOSTS`; in `llmaas` an
external host must be in `EGRESS_ALLOWLIST`. A refused host makes sign-in answer 503.

**Corporate CA.** Mount the bundle read-only into the backend and the background worker with a
compose override next to `compose.yaml`, then point `LDAP_CA_FILE` at it:

```yaml
# compose.override.yaml (the operator's file, not in the repository)
services:
  backend:
    volumes: ["/etc/pki/corp-ca.pem:/etc/ffcore/corp-ca.pem:ro"]
  agent-worker-bg:
    volumes: ["/etc/pki/corp-ca.pem:/etc/ffcore/corp-ca.pem:ro"]
```

`LDAP_CA_FILE=/etc/ffcore/corp-ca.pem`. A path that is not a file stops the start-up
(`ldap_ca_file_missing`); every other incoherent setting too (`ldap_plaintext_forbidden`,
`ldap_incomplete`, `ldap_filter_invalid`, `ldap_url_invalid`). `python scripts/compose_preflight.py
--env-file .env` reports the same before anything starts (`docs/kurulum.md`, "Preflight").

## Sign-in

The login form does not change. What happens is decided by the account, never by trying one
source after another:

1. The value typed matches a live account by email:
   - a **local** account signs in with its password (then `LOCAL_LOGIN` applies);
   - a **directory** account asks the directory.
2. No account matches and LDAP is on: the directory is asked (account name, UPN or email). On
   success the platform account is created (`auth_source=ldap`, `external_id` = the GUID, no
   password) and the group mappings are applied.
3. Then the usual session cookie (C6); the directory is not asked again until the next sign-in.

| Situation | Answer |
|---|---|
| wrong password, unknown login, empty password, several accounts match | 401 `invalid_credentials`, the same body every time; the reason is only in the audit row (`auth.login` `denied`, `after.reason`) |
| directory unreachable, timeout, service account refused, host refused by egress | 503 `identity_provider_unavailable`. **No fallback to a local password.** A local account (the superadmin) still signs in |
| directory account while `LDAP_URL` is empty | 503 `identity_provider_unavailable` (`reason: ldap_disabled`) |
| account disabled in the directory (`userAccountControl`) or in FFCore | 403 `user_inactive` |
| directory account without an email | 403 `identity_email_missing` |
| the email belongs to another account (for example a local pilot account) | 409 `identity_conflict` until a superadmin links it (below) |
| `LOCAL_LOGIN` forbids local passwords for this account | 403 `local_login_disabled` (only after a correct password) |
| a directory account calls `POST /auth/password` | 400 `external_identity` |

**`LOCAL_LOGIN`.** `all`: every local account. `superadmin_only` (recommended with a directory):
only the superadmin signs in with a local password. `off`: the same, and the login screen no
longer advertises local accounts (`GET /auth/providers` `local: false`). The superadmin can
always sign in locally, whatever the value: it is the recovery account when the directory is
down. A superadmin is always a local account (the database refuses anything else).

## Group mappings

A mapping says: members of this group get this role in this project.

```
provider  external_group                                  project   role     access
ldap      CN=FFCore-Chat,OU=Groups,DC=example,DC=com       support   user     read
ldap      CN=FFCore-Analysts,OU=Groups,DC=example,DC=com   support   analyst  edit
```

- LDAP group DNs compare case-insensitively (stored lower-case).
- Applied at **every** sign-in: a new mapping reaches members at their next sign-in, a removed
  one (or a member who left the group) loses that membership at the next sign-in.
- Several groups for one project: the highest role wins; `edit` beats `read`.
- A member in no mapped group signs in but belongs to no project (unless
  `DEFAULT_PROJECT_FOR_NEW_USERS` names one, which gives `user`/`read`).
- **Manual memberships win.** A membership an admin added or changed by hand
  (`membership_source=manual`) is never touched by the sync, even where a group maps the same
  project; changing a group-given membership on the members screen makes it manual. Removing a
  group-given membership by hand lasts only until the member's next sign-in while the mapping
  stays: remove the mapping (or the member from the group) instead.

API: `GET|POST /api/v1/projects/{project_id}/identity-mappings`,
`DELETE …/identity-mappings/{mapping_id}` (project admin with edit access, superadmin), and
`GET /api/v1/identity-mappings` (all projects, superadmin). Each answer carries
`affected_members`: how many directory-given memberships the project has (a number, no names).
Allowed roles: `user`, `analyst`, `admin`.

## Linking a local account (pilot users)

Pilot users have local accounts with the same email the directory now has. Their first directory
sign-in answers 409 `identity_conflict`: FFCore never joins two identities silently. A superadmin
links the account:

```
PATCH /api/v1/users/{user_id}   {"auth_source": "ldap"}
```

The local password is **deleted** and every session ends; the next directory sign-in with the same
email binds the account (memberships, conversations and memory stay). Audit:
`user_identity_linked` (`password_deleted: true`), then `user_identity_bound` at the sign-in.
Only a local, non-superadmin account can be linked; nothing is linked back.

## Deactivation (`identity_sync`)

A daily job on the background worker (04:15, arq cron) asks the directory about every active
directory account: one the directory no longer has or has disabled is deactivated
(`is_active=false`), its open sessions end at once, and `user_deactivated` is audited with the
reason (`directory_missing`, `directory_disabled`). OIDC accounts unused for
`OIDC_INACTIVE_AFTER_DAYS` are deactivated the same way (`oidc_inactive`). If the directory cannot
be reached the run changes **nothing** (no half run) and records `identity.sync` with
`outcome=error`; the provider status shows the last run.

## Importing local accounts (CSV)

For people outside the directory (contractors, test accounts) a superadmin imports a CSV:

```
email,full_name,role,access,project_keys
contractor@example.com,Contractor One,user,read,support;billing
```

`POST /api/v1/users/import` (multipart field `file`, at most 1 MiB and 5,000 rows) reports first
(`dry_run=true`, the default): each line is `create`, `update` or `error` with its line number
and code (`invalid_email`, `duplicate_email`, `invalid_full_name`, `invalid_role`,
`invalid_access`, `unknown_project`, `external_identity`, `row_columns`). A bad line never stops
the file. `dry_run=false` applies the good lines: a new account gets a temporary password that
appears **once**, in that answer, and is never stored in clear or audited; at the first sign-in
`must_change_password` sends the user to the password screen. Existing local accounts get the
name and the listed memberships (as manual). Directory accounts are refused: the directory
manages them. The audit row `user_imported` keeps the counts only.

FFCore does not e-mail the temporary passwords: a password in an e-mail outlives the first
sign-in. Hand them over the organisation's usual way.

## Provider status

`GET /api/v1/identity-providers` (superadmin): which providers are on, `ldaps` or `ldap`, the
number of accounts per source, `LOCAL_LOGIN`, the last `identity_sync`. No address, account or
password. `POST /api/v1/identity-providers/ldap/test` binds with the service account and returns
`ok`, the time taken and, on failure, a code (`service_bind_failed`, `directory_unreachable`,
`egress_*`). The console's Settings → Identity section shows both (17-3).

## Channels (package 15)

`ffcore.core.identity.resolve_external_identity(email | upn | external_id)` is the one place a
channel or widget identity becomes a platform account. It returns the live, active account or
nothing; with `AUTO_PROVISION_FROM_CHANNELS=true` a user the directory knows by email gets an
account first (group mappings applied). The widget's token exchange endpoint is package 15's.

## Audit events

`auth.login` (`after.source`: local, ldap; `after.reason` on refusals), `user_provisioned`,
`user_identity_linked`, `user_identity_bound`, `membership_synced` (project ids added, removed,
changed), `user_deactivated`, `identity.sync`, `user_imported`, `create_identity_mapping`,
`delete_identity_mapping`, `test_identity_provider`. No password, bind DN password or temporary
password is ever in an audit row, a log line or an API answer other than the import's one-time
answer.

## Not included

SAML, SCIM, MFA (the identity provider's), self sign-up, a different directory per project,
nested group resolution beyond what `memberOf` returns.
