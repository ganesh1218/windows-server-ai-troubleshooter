"""Review GitHub updates, then start the local connector from this checkout."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys

REMOTE = 'https://github.com/ganesh1218/windows-server-health-check.git'
ROOT = Path(__file__).resolve().parent


class LauncherError(Exception):
    pass


def git(root, *args):
    environment = dict(os.environ)
    environment['GIT_TERMINAL_PROMPT'] = '0'
    try:
        result = subprocess.run(['git', '-C', str(root), *args], capture_output=True,
                                text=True, encoding='utf-8', errors='replace', timeout=90,
                                env=environment, check=False)
    except FileNotFoundError as error:
        raise LauncherError('Git is not installed or is not on PATH. Install Git, or use the website ZIP connector.') from error
    except (OSError, subprocess.TimeoutExpired) as error:
        raise LauncherError('Git could not complete. No update was approved. Retry when GitHub is reachable.') from error
    if result.returncode:
        raise LauncherError('Git ' + args[0] + ' failed. Check repository access and network connectivity. No forced update was attempted.')
    return result.stdout.strip()


def normalized_remote(value):
    return value.strip().rstrip('/').removesuffix('.git').casefold()


def check_checkout(root):
    if Path(git(root, 'rev-parse', '--show-toplevel')).resolve() != root.resolve():
        raise LauncherError('Run launcher.py from its own complete Git checkout.')
    if normalized_remote(git(root, 'remote', 'get-url', 'origin')) != normalized_remote(REMOTE):
        raise LauncherError('Origin does not match the expected public GitHub repository. No code was updated or started.')
    if git(root, 'branch', '--show-current') != 'main':
        raise LauncherError('The launcher requires branch main. Keep other branches for development.')
    if git(root, 'status', '--porcelain', '--untracked-files=normal'):
        raise LauncherError('Local changes or untracked files exist. Review and save them first; the launcher never discards local work.')


def prepare(root=ROOT, offline=False, confirm=input, output=print):
    check_checkout(root)
    if offline:
        output('Offline mode: no GitHub update check. Using the current clean checkout.')
        return
    # Fetch only the fixed repository and main branch, not an arbitrary remote URL.
    git(root, 'fetch', '--no-tags', REMOTE, 'main')
    candidate = git(root, 'rev-parse', 'FETCH_HEAD')
    ahead, behind = map(int, git(root, 'rev-list', '--left-right', '--count', 'HEAD...' + candidate).split())
    if ahead:
        raise LauncherError('Local history is ahead or diverged. Resolve it manually; no reset or rebase was attempted.')
    if not behind:
        output('GitHub main is up to date.')
        return
    output('GitHub main has ' + str(behind) + ' new commit(s). Candidate: ' + candidate)
    output(git(root, 'log', '--format=%h %s', 'HEAD..' + candidate))
    output(git(root, 'diff', '--stat', 'HEAD', candidate))
    while True:
        answer = confirm('Review full diff [r], apply this fast-forward update [y], or start current code [n, default]: ').strip().lower()
        if answer == 'r':
            output(git(root, '--no-pager', 'diff', 'HEAD', candidate))
            continue
        if answer == 'y':
            # Recheck after review; do not overwrite edits made while waiting.
            check_checkout(root)
            git(root, 'merge', '--ff-only', '--no-edit', candidate)
            if git(root, 'rev-parse', 'HEAD') != candidate:
                raise LauncherError('Updated checkout does not match the approved commit. Connector not started.')
            check_checkout(root)
            output('Applied the approved GitHub commit.')
        else:
            output('Update declined. Starting the current checkout.')
        return


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline', action='store_true', help='Use the clean local checkout without checking GitHub')
    parser.add_argument('--diagnose', action='store_true', help='Run local readiness checks instead of starting the connector')
    args = parser.parse_args()
    if sys.platform != 'win32' or sys.version_info < (3, 11):
        print('Use Python 3.11 or newer on a Windows management computer.')
        return 1
    try:
        prepare(offline=args.offline)
        command = [sys.executable, str(ROOT / 'connector/connector.py')]
        if args.diagnose:
            command.append('--diagnose')
        # A fresh process loads all connector changes from the approved checkout.
        return subprocess.call(command, cwd=ROOT)
    except LauncherError as error:
        print(str(error))
        print('If only the network is unavailable, use --offline after reviewing your current local checkout.')
        return 1
    except (KeyboardInterrupt, EOFError):
        print('Launcher stopped. No unapproved update was applied.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
