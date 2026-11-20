"""Check installer branch selection without installing or accessing the network."""

import os
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[2]
INSTALLER_DIRS = [ROOT]
if (ROOT / "site/public/install.sh").exists():
    INSTALLER_DIRS.append(ROOT / "site/public")


@pytest.mark.skipif(shutil.which("bash") is None, reason="Bash unavailable")
@pytest.mark.parametrize("directory", INSTALLER_DIRS)
@pytest.mark.parametrize("branch", [None, "", "release-test"])
@pytest.mark.parametrize("method", ["gh", "token", "git"])
def test_shell_clone_branch(directory: Path, branch: str | None, method: str):
    script = (directory / "install.sh").read_text()
    assignment = next(
        line for line in script.splitlines() if line.startswith("AGENTGUARD_BRANCH=")
    )
    start = script.index("    CLONED=0\n")
    end = script.index("\n  fi\nfi\n", start)
    # Run only branch selection and clone dispatch with shell-function fakes.
    # No installer setup, filesystem deletion, or real git/gh command runs.
    harness = r'''
set -euo pipefail
gh() {
    if [[ "$1" == "auth" ]]; then return 0; fi
    [[ "$CLONE_METHOD" == "gh" ]] || return 1
    printf '%s\n' "$@"
}
git() { printf '%s\n' "$@"; }
APP_DIR="unused-app-dir"
REPO_URL="https://github.com/Sajibv1/AgentGuard.git"
'''
    env = dict(os.environ, CLONE_METHOD=method)
    env.pop("AGENTGUARD_BRANCH", None)
    env.pop("GITHUB_TOKEN", None)
    if branch is not None:
        env["AGENTGUARD_BRANCH"] = branch
    if method == "token":
        env["GITHUB_TOKEN"] = "test-placeholder"
    result = subprocess.run(
        ["bash", "-c", harness + assignment + "\n" + script[start:end]],
        env=env,
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    args = result.stdout.splitlines()
    assert args[args.index("--branch") + 1] == (branch or "main")
    expected_prefix = (
        ["repo", "clone", "Sajibv1/AgentGuard"]
        if method == "gh"
        else ["clone", "--depth", "1"]
    )
    assert args[:3] == expected_prefix
    if method == "token":
        assert "https://test-placeholder@github.com/Sajibv1/AgentGuard.git" in args


@pytest.mark.parametrize("directory", INSTALLER_DIRS)
def test_windows_clone_and_archive_default_to_main(directory: Path):
    script = (directory / "install.ps1").read_text()
    assert 'if (-not $Branch) { $Branch = "main" }' in script
    assert '[string]$Branch = $env:AGENTGUARD_BRANCH' in script
    assert 'clone --depth 1 -b $Branch $RepoUrl $AppDir' in script
    assert '$cleanRepo/archive/refs/heads/$Branch.zip' in script
    assert '"master"' not in script


@pytest.mark.skipif(len(INSTALLER_DIRS) < 2, reason="Website checkout unavailable")
@pytest.mark.parametrize("name", ["install.sh", "install.ps1"])
def test_website_installer_matches_runtime(name: str):
    assert (ROOT / name).read_text() == (ROOT / "site/public" / name).read_text()
