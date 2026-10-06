"""Executable debt-policy regressions using real Ruff and disposable Git histories."""

import json
import subprocess
import tomllib
from dataclasses import replace

import pytest

from scripts import check_complexity_policy as policy

pytestmark = pytest.mark.ci_fast
PIN = next(
    item
    for item in tomllib.loads((policy.ROOT / "pyproject.toml").read_text("utf-8"))[
        "project"
    ]["optional-dependencies"]["dev"]
    if item.startswith("ruff==")
)


def source(branches=16, *, name="hotspot", suppressed=True, ending="return -1"):
    comment = "  # noqa: C901" if suppressed else ""
    lines = [f"def {name}(value):{comment}"]
    for index in range(branches):
        lines.extend([f"    if value == {index}:", f"        return {index}"])
    return "\n".join(lines + [f"    {ending}"]) + "\n"


def measured(text, path="src/core/hotspot.py", root=policy.ROOT):
    return next(iter(policy.measure({path: text}, root).values()))


def allowance(item, identifier="reviewed-hotspot"):
    return policy.Allowance(
        identifier, item.path, item.symbol, item.complexity, "Reviewed KRT-36 fixture"
    )


def transition(before, after, *, new=None, old=None):
    old = old or allowance(before)
    new = new or replace(old, path=after.path, symbol=after.symbol)
    return policy.compare(
        {after.key: after}, {before.key: before}, {new.id: new}, {old.id: old}
    )


@pytest.fixture
def hotspot():
    return measured(source())


def test_executable_edit_cannot_preserve_complexity(hotspot):
    after = measured(source(ending="return -2"))
    report = transition(hotspot, after)
    assert report["hotspots"][0]["touched"]
    assert any("strict improvement" in message for message in report["failures"])


def test_complexity_and_ceiling_increases_fail(hotspot):
    after = measured(source(17))
    report = transition(hotspot, after, new=allowance(after))
    assert any("ceiling increased" in message for message in report["failures"])
    assert any("complexity increased" in message for message in report["failures"])


def test_reduction_requires_exact_ceiling_and_tightens(hotspot):
    after = measured(source(15))
    report = transition(hotspot, after)
    assert not report["failures"]
    assert report["adjustments"]
    lowered = report["proposed"]["reviewed-hotspot"]
    assert lowered.ceiling == 16
    assert not transition(hotspot, after, new=lowered)["adjustments"]


def test_tightening_never_raises_an_undersized_current_ceiling(hotspot):
    after = measured(source(15))
    entry = replace(allowance(hotspot), ceiling=15)
    report = transition(hotspot, after, new=entry)
    assert report["failures"]
    assert report["proposed"][entry.id].ceiling == 15


def test_suppression_and_allowance_expire_at_normal_limit(hotspot):
    after = measured(source(14, suppressed=False))
    report = transition(hotspot, after)
    assert not report["failures"]
    assert not report["proposed"]
    assert report["adjustments"]
    still_suppressed = measured(source(14))
    assert any(
        "obsolete C901 suppression" in error
        for error in transition(hotspot, still_suppressed)["failures"]
    )


def test_unreviewed_debt_fails_even_without_suppression():
    for text in (source(), source(suppressed=False), source(0)):
        item = measured(text)
        report = policy.compare({item.key: item}, {}, {}, {})
        assert any("unreviewed C901 debt" in error for error in report["failures"])


@pytest.mark.parametrize(
    "comment", ["# noqa", "# noqa: C", "# ruff: noqa: C901", "# flake8: noqa"]
)
def test_blanket_or_file_suppression_rejected(comment):
    with pytest.raises(ValueError, match="blanket"):
        policy.suppression_rows(f"{comment}\ndef f(): pass\n")


def test_noqa_text_in_strings_is_not_a_suppression():
    assert not policy.suppression_rows('message = "# noqa: C901"\n')


def test_unbound_suppression_fails():
    with pytest.raises(ValueError, match="unbound"):
        policy.callables("# noqa: C901\ndef f(): pass\n", "src/core/f.py", {2: 1})


def test_move_and_rename_keep_allowance_without_requiring_fake_improvement(hotspot):
    after = measured(source(name="renamed"), "src/services/moved.py")
    report = transition(hotspot, after)
    assert not report["failures"] + report["adjustments"]
    assert not report["hotspots"][0]["touched"]
    assert report["hotspots"][0]["id"] == "reviewed-hotspot"


def test_move_does_not_reset_ceiling_or_id(hotspot):
    after = measured(source(17, name="renamed"), "src/core/moved.py")
    report = transition(hotspot, after, new=allowance(after, "replacement-id"))
    assert any("identity reset" in error for error in report["failures"])


def test_format_comments_and_docstrings_are_not_touches(hotspot):
    text = source().replace("def hotspot(value):", "def hotspot( value ):")
    text = text.replace(
        "    if value == 0:",
        '    """New documentation."""\n    # explanation\n    if value == 0:',
    )
    report = transition(hotspot, measured(text))
    assert not report["failures"] + report["adjustments"]
    assert not report["hotspots"][0]["touched"]


@pytest.mark.parametrize("change", ["signature", "decorator"])
def test_signatures_and_decorators_are_executable_touches(hotspot, change):
    text = (
        source().replace("(value)", "(value=0)")
        if change == "signature"
        else "@decorator\n" + source()
    )
    assert any(
        "strict improvement" in error
        for error in transition(hotspot, measured(text))["failures"]
    )


def test_nested_async_callable_qualifications():
    text = "class Outer:\n    async def method(self):\n        def nested():\n            return 0\n        return nested()\n"
    items = policy.measure({"src/core/nested.py": text}, policy.ROOT)
    assert {key[1] for key in items} == {"Outer.method", "Outer.method.nested"}


def test_ambiguous_debt_and_missing_metrics_fail():
    text = source() + source()
    with pytest.raises(ValueError, match="ambiguous"):
        policy.measure({"src/core/duplicate.py": text}, policy.ROOT)
    with pytest.raises(ValueError, match="missing Ruff"):
        policy.callables("def f(): pass", "src/core/f.py", {})


@pytest.mark.parametrize(
    "mutation", ["duplicate", "empty_reason", "normal_ceiling", "schema", "container"]
)
def test_invalid_baselines_fail(hotspot, mutation):
    data = json.loads(policy.baseline_text({"reviewed-hotspot": allowance(hotspot)}))
    if mutation == "duplicate":
        data["allowances"] *= 2
    elif mutation == "schema":
        data["schema"] = 999
    elif mutation == "container":
        data = []
    elif mutation == "empty_reason":
        data["allowances"][0]["reason"] = " "
    else:
        data["allowances"][0]["ceiling"] = 15
    with pytest.raises(ValueError):
        policy.load_baseline(json.dumps(data))


@pytest.fixture
def repository(tmp_path):
    (tmp_path / "src/core").mkdir(parents=True)
    (tmp_path / "scripts").mkdir()
    (tmp_path / "pyproject.toml").write_text(
        f'''[project.optional-dependencies]
dev = ["{PIN}"]
[tool.ruff.lint]
select = ["C901"]
[tool.ruff.lint.mccabe]
max-complexity = 15
''',
        encoding="utf-8",
    )
    (tmp_path / "src/core/hotspot.py").write_text(source(), encoding="utf-8")
    subprocess.run(["git", "init", str(tmp_path)], capture_output=True, check=True)
    return tmp_path


def commit_fixture(root):
    policy.git(root, ["add", "."])
    policy.git(
        root,
        [
            "-c",
            "user.name=Policy test",
            "-c",
            "user.email=policy@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-m",
            "fixture",
        ],
    )


def write_allowance(root):
    item = measured(source(), root=root)
    (root / policy.BASELINE_PATH).write_text(
        policy.baseline_text({"reviewed-hotspot": allowance(item)}), encoding="utf-8"
    )


def test_initial_adoption_only_accepts_historical_suppression(repository):
    commit_fixture(repository)
    write_allowance(repository)
    report = policy.check(repository)
    assert not report["failures"] + report["adjustments"]
    # Inventing a baseline entry for newly added debt during adoption must fail.
    (repository / "src/core/hotspot.py").write_text(
        source(name="new"), encoding="utf-8"
    )
    new = measured(source(name="new"), root=repository)
    (repository / policy.BASELINE_PATH).write_text(
        policy.baseline_text({"new": allowance(new, "new")}), encoding="utf-8"
    )
    assert any(
        "unreviewed allowance" in error
        for error in policy.check(repository)["failures"]
    )


def test_committed_identity_move_and_regression_use_historical_measurements(repository):
    write_allowance(repository)
    commit_fixture(repository)
    old = policy.load_baseline((repository / policy.BASELINE_PATH).read_text())[
        "reviewed-hotspot"
    ]
    (repository / "src/core/hotspot.py").unlink()
    (repository / "src/core/moved.py").write_text(
        source(name="renamed"), encoding="utf-8"
    )
    moved = replace(old, path="src/core/moved.py", symbol="renamed")
    (repository / policy.BASELINE_PATH).write_text(
        policy.baseline_text({moved.id: moved}), encoding="utf-8"
    )
    assert not policy.check(repository)["failures"]
    (repository / "src/core/moved.py").write_text(
        source(17, name="renamed"), encoding="utf-8"
    )
    assert any(
        "complexity increased" in error
        for error in policy.check(repository)["failures"]
    )


def test_missing_git_history_fails_instead_of_skipping(repository):
    write_allowance(repository)
    with pytest.raises(ValueError, match="Git comparison history"):
        policy.check(repository, "missing-ref")


@pytest.mark.parametrize(
    "option", ["ignore", "select", "limit", "per_file", "alternate"]
)
def test_configuration_bypasses_fail(repository, option):
    config = tomllib.loads((repository / "pyproject.toml").read_text())
    lint = config["tool"]["ruff"]["lint"]
    if option == "limit":
        lint["mccabe"]["max-complexity"] = 16
    elif option == "ignore":
        lint["ignore"] = ["C9"]
    elif option == "select":
        lint["select"] = ["F"]
    elif option == "per_file":
        lint["per-file-ignores"] = {"src/**": ["C901"]}
    else:
        (repository / "src/core/.ruff.toml").write_text("", encoding="utf-8")
    assert policy.configuration_failures(config, repository)


def test_cli_reports_json_and_tightens_only_verified_reductions(
    repository, monkeypatch
):
    write_allowance(repository)
    commit_fixture(repository)
    (repository / "src/core/hotspot.py").write_text(source(15), encoding="utf-8")
    monkeypatch.setattr(policy, "ROOT", repository)
    assert policy.main(["--tighten", "--format", "json"]) == 0
    assert (
        policy.load_baseline((repository / policy.BASELINE_PATH).read_text())[
            "reviewed-hotspot"
        ].ceiling
        == 16
    )


def test_cli_failures_leave_baseline_unchanged(repository, monkeypatch, capsys):
    write_allowance(repository)
    commit_fixture(repository)
    baseline = repository / policy.BASELINE_PATH
    original = baseline.read_bytes()
    (repository / "src/core/hotspot.py").write_text(source(17), encoding="utf-8")
    monkeypatch.setattr(policy, "ROOT", repository)
    assert policy.main(["--tighten", "--format", "json"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["hotspots"][0]["previous"] == 17
    assert report["hotspots"][0]["current"] == 18
    assert report["hotspots"][0]["touched"]
    assert baseline.read_bytes() == original


def test_cli_check_is_read_only_and_tightening_removes_finished_debt(
    repository, monkeypatch
):
    write_allowance(repository)
    commit_fixture(repository)
    baseline = repository / policy.BASELINE_PATH
    original = baseline.read_bytes()
    (repository / "src/core/hotspot.py").write_text(
        source(14, suppressed=False), encoding="utf-8"
    )
    monkeypatch.setattr(policy, "ROOT", repository)
    assert policy.main(["--format", "json"]) == 1
    assert baseline.read_bytes() == original
    assert policy.main(["--tighten", "--format", "json"]) == 0
    assert not policy.load_baseline(baseline.read_text())


def test_cli_tightening_cannot_add_or_reset_allowances(repository, monkeypatch):
    write_allowance(repository)
    commit_fixture(repository)
    item = measured(source(), root=repository)
    reset = allowance(item, "reset-id")
    baseline = repository / policy.BASELINE_PATH
    baseline.write_text(policy.baseline_text({reset.id: reset}), encoding="utf-8")
    original = baseline.read_bytes()
    monkeypatch.setattr(policy, "ROOT", repository)
    assert policy.main(["--tighten", "--format", "json"]) == 1
    assert baseline.read_bytes() == original


def test_cli_deleted_callable_removes_allowance(repository, monkeypatch):
    write_allowance(repository)
    commit_fixture(repository)
    (repository / "src/core/hotspot.py").unlink()
    monkeypatch.setattr(policy, "ROOT", repository)
    assert policy.main(["--tighten", "--format", "json"]) == 0
    assert not policy.load_baseline((repository / policy.BASELINE_PATH).read_text())


def test_new_extracted_code_is_held_to_normal_limit(repository):
    write_allowance(repository)
    commit_fixture(repository)
    (repository / "src/core/helper.py").write_text(
        source(name="helper", suppressed=False), encoding="utf-8"
    )
    assert any(
        "helper: unreviewed C901 debt" in error
        for error in policy.check(repository)["failures"]
    )


def test_missing_ruff_is_an_actionable_failure(monkeypatch):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess([], 1, "", "No module named ruff"),
    )
    with pytest.raises(ValueError, match="No module named ruff"):
        policy.ruff(["--version"], policy.ROOT)
