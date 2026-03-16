import os
import subprocess


def _run(cmd):
    return subprocess.run(cmd, check=True, capture_output=True, text=True)


def _is_git_repo(path):
    return os.path.isdir(os.path.join(path, ".git"))


def ensure_repo(repo_url, branch, path):
    if not os.path.exists(path):
        _run(["git", "clone", "--branch", branch, repo_url, path])
        commit = _run(["git", "-C", path, "rev-parse", "HEAD"]).stdout.strip()
        return True, commit
    if not _is_git_repo(path):
        raise RuntimeError(f"path exists but is not a git repo: {path}")

    _run(["git", "-C", path, "fetch", "origin", branch])
    local = _run(["git", "-C", path, "rev-parse", "HEAD"]).stdout.strip()
    remote = _run(["git", "-C", path, "rev-parse", f"origin/{branch}"]).stdout.strip()
    if local != remote:
        _run(["git", "-C", path, "reset", "--hard", f"origin/{branch}"])
        return True, remote
    return False, local
