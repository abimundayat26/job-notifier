import subprocess
from typing import Callable

Runner = Callable[..., subprocess.CompletedProcess]


class PushFailedError(RuntimeError):
    pass


def commit_and_push_state(
    path: str,
    message: str,
    max_retries: int = 3,
    runner: Runner = subprocess.run,
) -> bool:
    """Commits and pushes the state file to main. On a push rejection
    (e.g. a manual commit landed between fetch and push), rebases onto
    origin/main and retries rather than failing the run (SPEC.md §14).

    Returns False if there was nothing to commit, True if a commit was pushed.
    """
    runner(["git", "add", path], check=True)

    status = runner(["git", "status", "--porcelain", path], check=True, capture_output=True, text=True)
    if not status.stdout.strip():
        return False

    runner(["git", "commit", "-m", message], check=True)

    for _ in range(max_retries):
        push = runner(["git", "push"], capture_output=True, text=True)
        if push.returncode == 0:
            return True
        runner(["git", "fetch", "origin", "main"], check=True)
        runner(["git", "rebase", "origin/main"], check=True)

    raise PushFailedError(f"failed to push state file after {max_retries} attempts")
