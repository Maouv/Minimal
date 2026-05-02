# vendored from aider/repo.py | commit: f09d70659ae90a0d068c80c288cbb55f2d3c3755
# stripped: GitRepo class (coupled ke aider io/prompts/utils)
# replaced: fungsi git standalone yang dibutuhkan minimal


try:
    import git

    ANY_GIT_ERROR: tuple[type[Exception], ...] = (
        git.exc.ODBError,
        git.exc.GitError,
        git.exc.InvalidGitRepositoryError,
        git.exc.GitCommandNotFound,
        OSError,
        IndexError,
        BufferError,
        TypeError,
        ValueError,
        AttributeError,
        AssertionError,
        TimeoutError,
    )
except ImportError:
    git = None
    ANY_GIT_ERROR = (OSError, ValueError)


def get_repo(cwd="."):
    if not git:
        return None
    try:
        return git.Repo(cwd, search_parent_directories=True)
    except ANY_GIT_ERROR:
        return None


def git_commit(message, fnames=None, cwd="."):
    """Commit files. Returns (hash, message) or None."""
    repo = get_repo(cwd)
    if not repo:
        return None
    try:
        if fnames:
            for f in fnames:
                repo.git.add(str(f))
        else:
            repo.git.add("-A")
        repo.git.commit("-m", message)
        sha = repo.head.commit.hexsha[:7]
        return sha, message
    except ANY_GIT_ERROR as e:
        raise RuntimeError(f"git commit failed: {e}")


def git_diff(cwd="."):
    """Return diff of last commit vs working tree."""
    repo = get_repo(cwd)
    if not repo:
        return ""
    try:
        return repo.git.diff("HEAD")
    except ANY_GIT_ERROR:
        return ""


def git_undo(cwd="."):
    """Undo last commit (keep changes staged)."""
    repo = get_repo(cwd)
    if not repo:
        raise RuntimeError("Not a git repo")
    try:
        repo.git.reset("--soft", "HEAD~1")
        return True
    except ANY_GIT_ERROR as e:
        raise RuntimeError(f"git undo failed: {e}")


def git_dirty_files(cwd="."):
    """Return list of modified files."""
    repo = get_repo(cwd)
    if not repo:
        return []
    try:
        staged = repo.git.diff("--name-only", "--cached").splitlines()
        unstaged = repo.git.diff("--name-only").splitlines()
        return list(set(staged + unstaged))
    except ANY_GIT_ERROR:
        return []
