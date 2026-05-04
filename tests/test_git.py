"""Tests for git integration module."""

import subprocess
import tempfile
from pathlib import Path

import pytest

from codewise.integrations.git import (
    GitError,
    get_repo_root,
    hooks_status,
    install_hooks,
    uninstall_hooks,
)


@pytest.fixture
def temp_git_repo():
    """Create a temporary git repository for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        subprocess.run(["git", "init"], cwd=tmpdir, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmpdir, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmpdir, capture_output=True)

        # Create an initial commit so HEAD exists
        test_file = Path(tmpdir) / "hello.py"
        test_file.write_text("print('hello')\n")
        subprocess.run(["git", "add", "."], cwd=tmpdir, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=tmpdir, capture_output=True)
        yield tmpdir


def test_get_repo_root(temp_git_repo):
    root = get_repo_root(temp_git_repo)
    assert root is not None
    assert Path(root).exists()


def test_get_repo_root_not_git():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = get_repo_root(tmpdir)
        assert root is None


def test_install_hooks(temp_git_repo):
    installed = install_hooks(temp_git_repo, pre_commit=True, pre_push=True)
    assert len(installed) == 2

    hooks_dir = Path(temp_git_repo) / ".git" / "hooks"
    pre_commit = hooks_dir / "pre-commit"
    pre_push = hooks_dir / "pre-push"

    assert pre_commit.exists()
    assert pre_push.exists()
    assert "codewise" in pre_commit.read_text().lower()
    assert "codewise" in pre_push.read_text().lower()


def test_install_hooks_no_overwrite(temp_git_repo):
    # Write a non-codewise hook
    hooks_dir = Path(temp_git_repo) / ".git" / "hooks"
    pre_commit = hooks_dir / "pre-commit"
    pre_commit.write_text("#!/bin/bash\necho 'other hook'")

    with pytest.raises(GitError, match="pre-commit hook already exists"):
        install_hooks(temp_git_repo, pre_commit=True, pre_push=False)


def test_install_hooks_force(temp_git_repo):
    hooks_dir = Path(temp_git_repo) / ".git" / "hooks"
    pre_commit = hooks_dir / "pre-commit"
    pre_commit.write_text("#!/bin/bash\necho 'other hook'")

    installed = install_hooks(temp_git_repo, pre_commit=True, pre_push=False, force=True)
    assert len(installed) == 1
    assert "codewise" in pre_commit.read_text().lower()


def test_uninstall_hooks(temp_git_repo):
    install_hooks(temp_git_repo)
    removed = uninstall_hooks(temp_git_repo)
    assert len(removed) == 2

    hooks_dir = Path(temp_git_repo) / ".git" / "hooks"
    assert not (hooks_dir / "pre-commit").exists()
    assert not (hooks_dir / "pre-push").exists()


def test_hooks_status(temp_git_repo):
    status = hooks_status(temp_git_repo)
    assert status["pre-commit"] == "not-installed"
    assert status["pre-push"] == "not-installed"

    install_hooks(temp_git_repo)
    status = hooks_status(temp_git_repo)
    assert status["pre-commit"] == "installed"
    assert status["pre-push"] == "installed"
