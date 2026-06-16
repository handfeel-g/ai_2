"""Codex Stop hook wrapper for auto-committing index.html only."""

from __future__ import annotations

import importlib.util
import platform
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def log_line(log_path: Path, status: str, detail: str = "") -> None:
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    message = f"{timestamp} | {status}"
    if detail:
        message = f"{message} | {detail}"
    with log_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(message + "\n")


def run_command(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )


def first_nonempty_line(value: str) -> str:
    for line in value.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def resolve_repo_root(script_dir: Path) -> Path:
    fallback_root = script_dir.parents[2]
    result = run_command(["git", "rev-parse", "--show-toplevel"], script_dir)
    if result.returncode == 0:
        detected = first_nonempty_line(result.stdout)
        if detected:
            return Path(detected)
    return fallback_root


def ensure_log_path(repo_root: Path) -> Path:
    log_dir = repo_root / ".codex" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "auto_commit_index_html.log"


def print_and_log(log_path: Path, status: str, detail: str = "", exit_code: int = 0) -> int:
    output = status if not detail else f"{status} {detail}"
    print(output)
    log_line(log_path, status, detail)
    return exit_code


def main() -> int:
    script_path = Path(__file__).resolve()
    repo_root = resolve_repo_root(script_path.parent)
    log_path = ensure_log_path(repo_root)

    log_line(
        log_path,
        "START",
        f"os={platform.platform()} python={sys.executable} cwd={Path.cwd()} repo_root={repo_root}",
    )

    git_path = shutil.which("git")
    if not git_path:
        return print_and_log(log_path, "GIT_NOT_AVAILABLE", "git executable not found", 1)

    git_version = run_command(["git", "--version"], repo_root)
    if git_version.returncode != 0:
        detail = first_nonempty_line(git_version.stderr) or "git --version failed"
        return print_and_log(log_path, "GIT_NOT_AVAILABLE", detail, 1)

    repo_check = run_command(["git", "rev-parse", "--is-inside-work-tree"], repo_root)
    if repo_check.returncode != 0 or first_nonempty_line(repo_check.stdout) != "true":
        detail = first_nonempty_line(repo_check.stderr) or "not a git repository"
        return print_and_log(log_path, "GIT_REPO_NOT_FOUND", detail, 1)

    git_root_output = run_command(["git", "rev-parse", "--show-toplevel"], repo_root)
    if git_root_output.returncode == 0:
        detected_root = first_nonempty_line(git_root_output.stdout)
        if detected_root:
            repo_root = Path(detected_root)
            log_path = ensure_log_path(repo_root)

    index_html = repo_root / "index.html"
    if not index_html.exists():
        return print_and_log(log_path, "INDEX_HTML_MISSING", str(index_html), 0)

    git_dir_result = run_command(["git", "rev-parse", "--git-dir"], repo_root)
    if git_dir_result.returncode != 0:
        detail = first_nonempty_line(git_dir_result.stderr) or "git dir not found"
        return print_and_log(log_path, "GIT_REPO_NOT_FOUND", detail, 1)

    git_dir = Path(first_nonempty_line(git_dir_result.stdout))
    if not git_dir.is_absolute():
        git_dir = repo_root / git_dir

    index_lock = git_dir / "index.lock"
    if index_lock.exists():
        return print_and_log(log_path, "GIT_INDEX_LOCK_PRESENT", str(index_lock), 1)

    user_name = first_nonempty_line(
        run_command(["git", "config", "--get", "user.name"], repo_root).stdout
    )
    user_email = first_nonempty_line(
        run_command(["git", "config", "--get", "user.email"], repo_root).stdout
    )
    if not user_name or not user_email:
        detail = f"user.name={'set' if user_name else 'missing'} user.email={'set' if user_email else 'missing'}"
        return print_and_log(log_path, "GIT_USER_IDENTITY_MISSING", detail, 1)

    log_line(log_path, "ENV_CHECK_OK", f"git={git_path} user.name={user_name} user.email={user_email}")

    status_result = run_command(["git", "status", "--porcelain", "--", "index.html"], repo_root)
    if status_result.returncode != 0:
        detail = first_nonempty_line(status_result.stderr) or "git status failed"
        return print_and_log(log_path, "GIT_STATUS_FAILED", detail, 1)

    if not first_nonempty_line(status_result.stdout):
        return print_and_log(log_path, "NO_INDEX_HTML_CHANGE")

    log_line(log_path, "INDEX_HTML_CHANGED")

    add_result = run_command(["git", "add", "--", "index.html"], repo_root)
    if add_result.returncode != 0:
        detail = first_nonempty_line(add_result.stderr) or "git add failed"
        return print_and_log(log_path, "GIT_ADD_FAILED", detail, 1)

    pre_commit_spec = importlib.util.find_spec("pre_commit")
    if pre_commit_spec is None:
        print_and_log(log_path, "PRE_COMMIT_NOT_INSTALLED_SKIP")
    else:
        pre_commit_result = run_command(
            [sys.executable, "-m", "pre_commit", "run", "--files", "index.html"],
            repo_root,
        )
        if pre_commit_result.returncode != 0:
            detail = first_nonempty_line(pre_commit_result.stderr) or "pre-commit failed"
            return print_and_log(log_path, "PRE_COMMIT_FAILED", detail, 1)

    add_after_result = run_command(["git", "add", "--", "index.html"], repo_root)
    if add_after_result.returncode != 0:
        detail = first_nonempty_line(add_after_result.stderr) or "git add after pre-commit failed"
        return print_and_log(log_path, "GIT_ADD_FAILED", detail, 1)

    staged_result = run_command(["git", "diff", "--cached", "--quiet", "--", "index.html"], repo_root)
    if staged_result.returncode == 0:
        return print_and_log(log_path, "NO_STAGED_INDEX_HTML_CHANGE")
    if staged_result.returncode != 1:
        detail = first_nonempty_line(staged_result.stderr) or "git diff --cached failed"
        return print_and_log(log_path, "GIT_DIFF_FAILED", detail, 1)

    commit_result = run_command(["git", "commit", "-m", "auto: update index.html"], repo_root)
    if commit_result.returncode != 0:
        detail = first_nonempty_line(commit_result.stderr) or "git commit failed"
        return print_and_log(log_path, "GIT_COMMIT_FAILED", detail, 1)

    hash_result = run_command(["git", "rev-parse", "HEAD"], repo_root)
    commit_hash = first_nonempty_line(hash_result.stdout) if hash_result.returncode == 0 else ""
    detail = commit_hash if commit_hash else "unknown"
    return print_and_log(log_path, "COMMIT_SUCCESS", detail)


if __name__ == "__main__":
    raise SystemExit(main())
