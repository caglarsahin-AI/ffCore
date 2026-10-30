"""The F table for every e2e run under tests/e2e (13b, K-13b-0001 S2; tests/e2e/ftable.py).

After the run the table is printed in the terminal summary; `--f-table <path>` also writes it
as Markdown (`make e2e` passes a path under eval/results/). Results are taken from each test's
call phase, or from setup when the test never got there (a skip or an error in a fixture).
"""

from pathlib import Path

from tests.e2e import ftable

_RESULTS: list[ftable.Result] = []


def pytest_addoption(parser):
    parser.addoption("--f-table", default=None, help="write the F table as Markdown to this path")


def pytest_runtest_logreport(report):
    if report.when == "call" or (report.when == "setup" and report.outcome != "passed"):
        reason = ""
        if report.skipped and isinstance(report.longrepr, tuple):
            reason = str(report.longrepr[2]).removeprefix("Skipped: ")
        _RESULTS.append(ftable.Result(report.nodeid, report.outcome, reason))


def pytest_terminal_summary(terminalreporter, config):
    if not _RESULTS:
        return
    table = ftable.markdown(ftable.summarize(_RESULTS, ftable.load_known()))
    terminalreporter.write_sep("=", "F table (plan/18)")
    terminalreporter.write(table)
    target = config.getoption("--f-table")
    if target:
        Path(target).parent.mkdir(parents=True, exist_ok=True)
        Path(target).write_text(table, encoding="utf-8")
        terminalreporter.write_line(f"F table written to {target}")
