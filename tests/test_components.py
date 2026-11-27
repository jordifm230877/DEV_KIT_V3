"""A project of several components names them once; a check may be for one of them, and
so may an audit, by day or at night."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from conftest import Project
from test_component_checks import CODER, _check, ran
from test_night import AUDITS as COUNTS
from test_night import HELLO
from test_settings_files import included

COMPONENTS = '[components]\nauth = ["auth/**"]\nlogin = ["login/**", "shared/login/**"]\n'
# A stand-in auditor that keeps what it was told beside its script.
TOLD = (
    "import re\nreport = pathlib.Path(re.search(r'docs/audits/\\S+\\.md', prompt).group(0))\n"
    "pathlib.Path(sys.argv[0]).with_name('brief.txt').write_text(prompt)\n"
    "report.parent.mkdir(parents=True, exist_ok=True)\nreport.write_text('# Findings\\n')\n"
    "print('RESULT: done')"
)


def report(kind: str, component: str) -> str:
    return f"docs/audits/{date.today()}-{kind}-audit-of-{component}.md"


def test_a_check_for_a_component_runs_when_the_component_changed(project: Project) -> None:
    for_auth = _check(project, "checks", "auth").replace(
        'paths = ["auth/**"]', 'component = "auth"'
    )
    for_login = _check(project, "checks", "lint").replace(
        'paths = ["lint/**"]', 'component = "login"'
    )
    project.configure(coder=CODER, settings=COMPONENTS + for_auth + for_login)
    project.dk("add", "shared/login/a.txt", "--spec", "a")

    project.dk("run")

    assert ran(project) == ["lint"]
    assert "left out, nothing of theirs changed: auth" in project.dk("show", "1")


def test_a_check_for_a_component_nobody_named_is_refused(project: Project) -> None:
    check = '[checks.auth]\nrun = ["true"]\ncomponent = "auht"\n'
    project.configure(coder=CODER, settings=COMPONENTS + check)

    refused = project.refused("run")

    assert "check 'auth' is for the component 'auht'" in refused and "auth, login" in refused


def test_the_paths_of_a_component_are_a_list(project: Project) -> None:
    """One path written without brackets was read as a list of its letters."""
    project.configure(coder=CODER, settings='[components]\nauth = "auth/**"\n')

    assert "component 'auth' takes a list of paths" in project.refused("run")


def test_one_component_is_audited_and_its_report_is_its_own(project: Project) -> None:
    project.configure(coder=HELLO, auditor=TOLD, settings=COMPONENTS)

    said = project.dk("audit", "security", "login", "--note", "Mind the tokens.")
    project.dk("run")

    assert report("security", "login") in said
    assert project.merged(report("security", "login")) == "# Findings\n"
    assert "#1 done  Security audit of login" in project.dk("status")
    told = Path(project.root.parent / "tools" / "brief.txt").read_text()
    assert "only at the component 'login'" in told and "login/**, shared/login/**" in told
    assert "Mind the tokens." in told and "secrets" in told


def test_an_audit_of_a_component_nobody_named_is_refused(project: Project) -> None:
    project.configure(coder=HELLO, auditor=TOLD, settings=COMPONENTS)

    refused = project.refused("audit", "security", "billing")

    assert "no component 'billing'" in refused and "auth, login" in refused
    assert project.dk("status") == ""


def test_at_night_each_component_is_audited_and_not_the_whole(project: Project) -> None:
    project.configure(coder=HELLO, auditor=COUNTS, settings=COMPONENTS)

    project.dk("night")

    status = project.dk("status")
    assert status.count("done") == 6 and status.count(" of auth") == 3
    assert project.merged(report("tests", "login")) is not None
    assert project.merged(f"docs/audits/{date.today()}-tests-audit.md") is None


def test_at_night_only_the_components_that_changed_are_audited_again(project: Project) -> None:
    project.configure(coder=HELLO, auditor=COUNTS, settings=COMPONENTS)
    project.dk("night")
    included(project, "shared/login/new.txt", "more\n")
    included(project, "elsewhere/new.txt", "more\n")

    said = project.dk("night")

    assert said.count("of auth: nothing changed since its last report") == 3
    status = project.dk("status")
    assert len(status.splitlines()) == 9 and status.count(" of login") == 6


def test_a_project_may_have_the_whole_audited_at_night_as_well(project: Project) -> None:
    whole = "[audit]\nwhole_project_at_night = true\n"
    project.configure(coder=HELLO, auditor=COUNTS, settings=COMPONENTS + whole)

    project.dk("night")

    assert project.dk("status").count("done") == 9
    assert project.merged(f"docs/audits/{date.today()}-tests-audit.md") is not None
    included(project, "elsewhere/new.txt", "more\n")
    said = project.dk("night")
    assert said.count("nothing changed since its last report") == 6
    assert len(project.dk("status").splitlines()) == 12
