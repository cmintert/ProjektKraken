"""Verify that local push and release gates retain their critical checks."""

import os
import subprocess
from pathlib import Path

import pytest

from scripts import install_hooks, preflight
from scripts.preflight import make_steps

pytestmark = pytest.mark.ci_fast


def test_push_runs_deep_quality_and_curated_regressions() -> None:
    """Every normal push must verify more than the remote smoke suite."""
    commands = [" ".join(command) for _, command in make_steps("push", "base123")]
    assert len(commands) == 9
    assert any("smoke or ci_fast" in value for value in commands)
    assert any("scripts.check_test_policy" in value for value in commands)
    assert any(
        "scripts.check_complexity_policy --base-ref base123" in value
        for value in commands
    )
    assert any(
        "scripts.check_visual_policy --base-ref base123" in value for value in commands
    )
    assert any("mypy src" in value for value in commands)
    assert any("-m sphinx -n -W" in value for value in commands)
    assert all("--update" not in value for value in commands)


def test_release_checks_entire_suite_without_double_fast_run() -> None:
    """A release candidate requires the full tests and coverage."""
    commands = [" ".join(command) for _, command in make_steps("release", "base123")]
    assert len(commands) == 9
    assert any("--cov=src" in value for value in commands)
    assert all("smoke or ci_fast" not in value for value in commands)


def git(root: Path, *args: str, check: bool = True, env=None):
    """Run Git in a disposable repository without global configuration."""
    return subprocess.run(
        ["git", "-c", f"safe.directory={root.as_posix()}", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=check,
        env=env,
    )


@pytest.fixture
def hooked_repo(tmp_path, monkeypatch):
    """Install the real push hook with cheap probe checks in a local Git repo."""
    root = tmp_path / "repo with spaces"
    root.mkdir()
    git(root, "init", "-b", "main")
    git(root, "config", "user.name", "Hook Test")
    git(root, "config", "user.email", "hook@example.invalid")
    scripts = root / "scripts"
    scripts.mkdir()
    # Exercise the actual validator/runner through Git's native hook protocol.
    (scripts / "preflight.py").write_text(
        "import importlib.util, os, pathlib, sys\n"
        f"spec = importlib.util.spec_from_file_location('gate', {str(Path(preflight.__file__).resolve())!r})\n"
        "gate = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(gate)\n"
        "gate.ROOT = pathlib.Path.cwd()\n"
        "probe = ('from pathlib import Path; "
        'Path("tracked.txt").write_text("changed during checks")\') '
        "if os.environ.get('TEST_CHECK_DIRTY') else "
        "'raise SystemExit(' + os.environ.get('TEST_CHECK_EXIT', '0') + ')'\n"
        "gate.make_steps = lambda mode, base: [('Probe', [sys.executable, '-c', "
        "probe])]\n"
        "raise SystemExit(gate.main())\n",
        encoding="utf-8",
    )
    (root / "tracked.txt").write_text("committed\n", encoding="utf-8")
    (root / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-m", "fixture")
    head = git(root, "rev-parse", "HEAD").stdout.strip()
    git(root, "update-ref", "refs/remotes/origin/main", head)
    remote = tmp_path / "remote.git"
    git(root, "init", "--bare", str(remote))
    git(root, "remote", "add", "origin", str(remote))
    monkeypatch.setattr(preflight, "ROOT", root)
    monkeypatch.setattr(install_hooks, "ROOT", root)
    install_hooks.install_push_hook()
    return root, remote, head


def test_native_hook_accepts_clean_head_and_annotated_tag(hooked_repo):
    root, remote, head = hooked_repo
    git(root, "tag", "-a", "beta", "-m", "beta")
    git(root, "push", "origin", "main", "refs/tags/beta")
    assert (
        git(root, "--git-dir", str(remote), "rev-parse", "main").stdout.strip() == head
    )


@pytest.mark.parametrize("change", ["unstaged", "staged", "untracked"])
def test_native_hook_rejects_local_changes(hooked_repo, change):
    root, remote, _ = hooked_repo
    name = "untracked.txt" if change == "untracked" else "tracked.txt"
    (root / name).write_text("local fix\n", encoding="utf-8")
    if change == "staged":
        git(root, "add", name)
    result = git(root, "push", "origin", "main", check=False)
    assert result.returncode != 0
    assert "clean checkout" in result.stderr
    assert git(root, "--git-dir", str(remote), "show-ref", check=False).returncode != 0


def test_native_hook_rejects_additional_non_head_ref(hooked_repo):
    root, remote, _ = hooked_repo
    git(root, "branch", "other")
    (root / "tracked.txt").write_text("new commit\n", encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-m", "second")
    result = git(root, "push", "origin", "main", "other", check=False)
    assert result.returncode != 0
    assert "does not match HEAD" in result.stderr
    assert git(root, "--git-dir", str(remote), "show-ref", check=False).returncode != 0


def test_native_hook_blocks_failed_check(hooked_repo):
    root, remote, _ = hooked_repo
    env = dict(os.environ, TEST_CHECK_EXIT="7")
    result = git(root, "push", "origin", "main", check=False, env=env)
    assert result.returncode != 0
    assert "FAILED Probe" in result.stderr
    assert git(root, "--git-dir", str(remote), "show-ref", check=False).returncode != 0


def test_native_hook_rejects_tree_changed_during_checks(hooked_repo):
    root, remote, _ = hooked_repo
    result = git(
        root,
        "push",
        "origin",
        "main",
        check=False,
        env=dict(os.environ, TEST_CHECK_DIRTY="1"),
    )
    assert result.returncode != 0
    assert "Push state changed during verification" in result.stderr
    assert git(root, "--git-dir", str(remote), "show-ref", check=False).returncode != 0


def test_native_hook_allows_deletion_without_validating_dirty_tree(hooked_repo):
    root, remote, _ = hooked_repo
    git(root, "push", "origin", "main:temporary")
    (root / "tracked.txt").write_text("local draft\n", encoding="utf-8")
    git(root, "push", "origin", ":temporary")
    assert git(root, "--git-dir", str(remote), "show-ref", check=False).returncode != 0


def test_installer_preserves_unrelated_push_hook(hooked_repo):
    root, _, _ = hooked_repo
    hook = root / ".git/hooks/pre-push"
    hook.write_text("#!/bin/sh\nexit 42\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="Existing push hook"):
        install_hooks.install_push_hook()
    assert hook.read_text(encoding="utf-8") == "#!/bin/sh\nexit 42\n"


def test_installer_migrates_old_pre_commit_push_wrapper(hooked_repo):
    root, _, _ = hooked_repo
    hook = root / ".git/hooks/pre-push"
    hook.write_text(
        "# File generated by pre-commit\nARGS=(--hook-type=pre-push)\n",
        encoding="utf-8",
    )
    install_hooks.install_push_hook()
    assert install_hooks.MARKER in hook.read_text(encoding="utf-8")


def test_installer_preserves_legacy_push_hook(hooked_repo):
    root, _, _ = hooked_repo
    legacy = root / ".git/hooks/pre-push.legacy"
    legacy.write_text("#!/bin/sh\nexit 42\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="legacy push hook"):
        install_hooks.install_push_hook()
    assert legacy.read_text(encoding="utf-8") == "#!/bin/sh\nexit 42\n"


def test_missing_base_is_actionable(monkeypatch):
    def missing(*args):
        raise RuntimeError("missing ref")

    monkeypatch.setattr(preflight, "git_output", missing)
    with pytest.raises(RuntimeError, match="git fetch origin main"):
        preflight.resolve_base_ref(None)


def test_missing_tool_returns_failure(monkeypatch):
    monkeypatch.setattr(preflight, "resolve_base_ref", lambda explicit: "base123")
    monkeypatch.setattr(
        preflight,
        "make_steps",
        lambda *args: [("Missing", ["kraken_missing_tool"])],
    )
    assert preflight.main(["push"]) == 1


def test_old_pre_commit_wrapper_fails_closed(monkeypatch):
    monkeypatch.setenv("PRE_COMMIT", "1")
    with pytest.raises(SystemExit) as error:
        preflight.main(["push"])
    assert error.value.code == 2


def test_malformed_hook_input_fails_closed():
    with pytest.raises(RuntimeError, match="four fields"):
        preflight.validate_push("refs/heads/main invalid\n")
