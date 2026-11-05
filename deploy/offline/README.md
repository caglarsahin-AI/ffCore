# Offline transport (package 19, the PoC subset of 12)

The PayCore server has no internet. Everything it needs for FFCore travels as an archive built
on an internet-connected preparation machine, and is checked on the server against lists kept in
this git repository, not against anything inside the archive.

| File | Where it runs | What it does |
|---|---|---|
| `images.txt` | (list) | every image: registry digest (checked after `docker pull`) and image id (checked after `docker load`) |
| `models.txt` | (list) | every model weight file: Hugging Face revision, path, SHA-256, size |
| `save.sh` | preparation machine | pull + provenance check, build ids printed for `images.txt`, `docker save`, `models.tar` (only the `models.txt` files), `manifest.sha256` |
| `load.sh` | server | `sha256sum -c` (transport), `docker load`, `models.tar` into the host models directory, then `verify.sh` |
| `verify.sh` | server | loaded image ids and model files against `images.txt` / `models.txt`; a hub model directory or snapshot file not in `models.txt` fails (named, never deleted) |
| `models-files.sh` | (helper) | the `models.txt` paths in the volume, for `save.sh` and `verify.sh` |

Why image ids on the server: `docker load` on the overlay2 image store does not keep
`RepoDigests`, so a registry digest cannot be read back after transport. The id (config digest)
survives save/load; the registry digest is checked where the registry is reachable.

Compose files refer to every image by the **tag** listed in `images.txt` (never `tag@digest`:
after `docker load` such a reference does not resolve and the service does not start). `save.sh`
pulls `repo@registry_digest` and tags the result with that name; on the server `verify.sh`'s
image id check takes the place of the digest in the reference. This works on both image
stores (overlay2 and containerd); which one the PayCore server uses is not verified.

`ffcore/backend` and `ffcore/frontend` are built from the release checkout; their ids are
`PENDING` until `save.sh` prints them and they are committed. `verify.sh` fails on `PENDING`.

Signatures (cosign/GPG) are package 12. The transport medium is assumed to stay in the user's
hands; `manifest.sha256` proves the archive arrived intact, the git lists prove it is the
pinned content.

Every script takes `--help` and `--dry-run`. The full server procedure is the paycoreLLM runbook
`docs/paycore/m3-sunucu.md`.
