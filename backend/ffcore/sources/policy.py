"""Who registers a data source of each kind (16-1 r1 MAJOR-1, decision A; KARARLAR '16-1 r1
kararları'). One table, read by the API.

A network folder is the installation's: one FS_SOURCES_BASE for every project, mounted by the
operator. Which folder a project may index is decided by the superadmin, who knows the share;
a project role registering `.` would index every department's files (review S3). So the
registration of an `fs` source and every change of what it reads (root, filters) need the
superadmin. Kinds whose credentials the project brings (Confluence, Jira, SharePoint: the
project's own service account decides what is visible) stay with the project admin. Everything
else (name, schedule, mode, ratio, pause, sync, permission mappings, reading) follows the
data-source routes' project roles.
"""

SUPERADMIN = "superadmin"
PROJECT_ADMIN = "project_admin"

REGISTRATION = {
    "fs": SUPERADMIN,
    "confluence": PROJECT_ADMIN,
    "jira": PROJECT_ADMIN,
    "sharepoint": PROJECT_ADMIN,
}
# Fields of an update that change what the source reads or how it authenticates.
READS = ("config", "secret")


def registrar(kind: str) -> str:
    """The rule for a kind; a kind missing here is a programming error (KeyError)."""
    return REGISTRATION[kind]


def config_change_needs_registrar(update: dict) -> bool:
    return any(update.get(field) is not None for field in READS)
