"""ENV rule judges `.env` only in argument/redirection position
(fix/ajan-hooklari-2, FOLLOWUP-189 e, K-HOOK2-0002; warn day: three coordinator
false positives on 16 Nov 22:26-22:35 where `.env` was text, not a path)."""

from __future__ import annotations

import pytest
from conftest import base_env, bash


def env_hit(guard, command: str, main_root) -> bool:
    found = guard.decide(bash(command), base_env(main_root, FFCORE_ROL="isci-b"))
    return any(v.rule == "ENV" for v in found)


@pytest.mark.parametrize(
    "cmd",
    [
        "cat .env",
        "source .env",
        ". ./.env",
        "set -a; . backend/.env; set +a",
        "cat '.env'",
        'cat ".env"',
        "grep KEY .env",
        "grep -n KEY -- .env",
        "grep -f .env x",
        "echo X >> .env",
        "echo X>.env",
        "cp .env.example .env",
        "docker compose --env-file .env up",
        "docker compose --env-file=.env up",
        "docker run -v ./.env:/app/.env img",
        "cat .ENV",
        "cat .env*",
        "sh -c 'cat .env'",
        "bash -o pipefail -c 'cat .env | head'",
        "echo $(cat .env)",
        "{ cat .env; }",
        "env X=1 cat .env",
        "docker compose run --rm tools cat .env",
        "for f in .env; do cat $f; done",
        "rg -n KEY .env",
    ],
)
def test_env_path_blocked(guard, main_root, cmd):
    assert env_hit(guard, cmd, main_root), cmd


@pytest.mark.parametrize(
    "cmd",
    [
        "grep -rn --exclude-dir=node_modules --exclude='.env' KEY .",
        "grep -rn --exclude=.env KEY .",
        'grep -n "\\.env" .gitignore',
        "grep -n .env .gitignore",
        "grep -e .env -e KEY docs/x.md",
        "rg -g '!.env' KEY",
        'echo "the .env file is not read"',
        "echo 'see .env.example'",
        'git commit -m "docs: .env is never read"',
        "cat > /tmp/x.md <<'EOF'\nthe .env file stays local\ncat .env\nEOF",
        "cat <<EOF > x\n.env\nEOF\necho done",
        "cat .env.test",
        "cat .env.example",
        "ls .envrc",
        "docker compose --env-file .env.test up",
        'printf "%s\\n" "no .env here"',
    ],
)
def test_env_text_allowed(guard, main_root, cmd):
    assert not env_hit(guard, cmd, main_root), cmd


def test_command_after_heredoc_still_checked(guard, main_root):
    assert env_hit(guard, "cat > x <<'EOF'\ntext\nEOF\ncat .env", main_root)
