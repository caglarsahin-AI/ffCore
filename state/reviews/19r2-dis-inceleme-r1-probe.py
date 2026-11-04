"""Reviewer probe for paycoreLLM fix/19r2-dis-inceleme r1 (1dce5e5): R9 fences, R10 technical `@`,
FOLLOWUP-160, on synthetic text only. Imports scripts/ffcore_stage_raw.py from a git archive copy
with its `paycore_llm` imports removed (the probed functions do not use them); no data/, eval/results/ or .env.

python 19r2-dis-inceleme-r1-probe.py <archive copy root>
"""

import re
import sys
import types

root = sys.argv[1]
# Load the script's own source without its paycore_llm imports: the functions probed here
# (_scrub, _mentions, _fenced, _drop_signatures, _heading and their regexes) use only re/Counter/sys.
source = open(f"{root}/scripts/ffcore_stage_raw.py", encoding="utf-8").read()
source = re.sub(r"^from paycore_llm[^\n(]*(\([^)]*\))?[^\n]*", "", source, flags=re.M)
m = types.ModuleType("stage_raw")
exec(compile(source, "ffcore_stage_raw.py", "exec"), m.__dict__)

LOGIN = "@ahmet.yilmaz"


def show(name, text):
    m._STATS.clear()
    out = m._scrub(text)
    leaked = LOGIN in out or "@ali.veli" in out or "@mehmet.kaya" in out
    print(f"{'LEAK ' if leaked else 'ok   '} {name}: {out!r} dropped={m._STATS['last_dropped']}")


cases = {
    # external report inputs (R9)
    "one-line {code} + mention + signature": "{code}SELECT 1{code} @ali.veli bakar mısın\n--\nAli Veli\nPayCore",
    "unclosed fence then mention": "```\nkod\n@ali.veli bak",
    "single backtick then mention": "`x @ali.veli bak",
    "two-line {code} keeps @Inject/@foo": "{code}\n@Inject @foo\n{code}\n@ali.veli bak",
    # reviewer spellings
    "{noformat} one line": "{noformat}x{noformat} @ali.veli",
    "~~~ block then prose": "~~~\n@foo\n~~~\n@ali.veli bak",
    "indented fence": "   ```python\n@foo\n   ```\n@ali.veli bak",
    "{code:sql}SELECT{code} @ali.veli": "{code:sql}SELECT{code} @ali.veli",
    "CRLF fences": "```\r\n@foo\r\n```\r\n@ali.veli bak\r\n",
    "fence in fence: ~~~ closed by ```": "~~~\n```\n~~~\n@ali.veli bak\n```",
    "fence in fence: {code} closed by {noformat}": "{code}\n{noformat}\n{code}\n@ali.veli bak\n{code}",
    "4-backtick block with ``` inside": "````\n```\n````\n@ali.veli bak\n```",
    "{{...}} inline (decision: code)": "{{@ali.veli}} ve @mehmet.kaya",
    "info string with a space (``` sql)": "``` sql\nSELECT 1\n```\n@ali.veli bak\n```\nx\n```",
    "info string with attrs (```js title=a)": "```js title=a\nx\n```\n@ali.veli bak\n```\ny\n```",
    "~~~~ (4 tildes)": "~~~~\n~~~\n~~~~\n@ali.veli bak\n~~~",
    "{code:title=A b}": "{code:title=A b|borderStyle=solid}\n@foo\n{code}\n@ali.veli bak",
    # R10
    "DECLARE @x": "DECLARE @x INT",
    "SET @x =": "SET @x = 1",
    "lutfen @ahmet.yilmaz bak": f"lutfen {LOGIN} bak",
    "login alone on a line (Jira reply)": f"{LOGIN}\nKontrol eder misin?",
    "login alone + punctuation": f"{LOGIN},\nKontrol eder misin?",
    "two logins on one line": f"{LOGIN} @mehmet.kaya",
    "login = assignment-like prose": f"Sorumlu: {LOGIN} = onaylayan",
    "login => arrow prose": f"{LOGIN} => devraldı",
    "uppercase SELECT prose": f"SELECT {LOGIN} ekibinden",
    "lowercase set prose": f"set {LOGIN} olarak",
    "decorator line": "@pytest.fixture\ndef x(): pass",
    # r2 additions (decision A, MINOR-1)
    "chained decorators then def": "@pytest.fixture\n@pytest.mark.slow\n\ndef x(): pass",
    "decorator then class": "@dataclass\nclass A: pass",
    "async def after decorator": "@app.get('/x')\nasync def f(): pass",
    "login alone at the end": f"Soru:\n{LOGIN}",
    "login alone then blank then prose": f"{LOGIN}\n\nKontrol eder misin?",
    "login alone then another login line": f"{LOGIN}\n@mehmet.kaya\nbakın",
    "login alone then def prose": f"{LOGIN}\ndefinitely bak",
    "DECLARE @x = 1": "DECLARE @x = 1",
    "lowercase declare assignment": "declare @ali.veli = 1",
    "login = 1 without SQL": "@ali.veli = 1",
    "@echo off": "@echo off",
    "@echo then login line": f"@echo {LOGIN}",
    # FOLLOWUP-160
    "@ahmet-yilmaz@firma.com": "iletişim @ahmet-yilmaz@firma.com",
    "@app_get(": "@app_get(path)",
    "@al short": "@al bak",
}
for name, text in cases.items():
    show(name, text)
print("heading:", m._heading(f"Özet {LOGIN} ve {{{{@ali.veli}}}}"))
print("heading alone:", m._heading(LOGIN))
