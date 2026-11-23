#!/usr/bin/env bash
# Create/push only when the caller explicitly supplies the remote and visibility.
set -euo pipefail
if [[ $# -ne 2 || ! "$1" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ || ( "$2" != "private" && "$2" != "public" ) ]]; then
    echo "Usage: bash tools/publish_github.sh OWNER/REPOSITORY private|public" >&2
    exit 2
fi
ffvit_repo=$(cd "$(dirname "$0")/.." && pwd)
cd "$ffvit_repo"
command -v gh >/dev/null
git lfs version >/dev/null
gh auth status
python3 -B tools/verify_repository.py
git diff --exit-code
git diff --cached --exit-code
if [[ -n $(git ls-files --others --exclude-standard) ]]; then
    echo 'Untracked archive files exist; commit the intended archive first.' >&2
    exit 2
fi
if git remote get-url origin >/dev/null 2>&1; then
    ffvit_remote=$(git remote get-url origin)
    if [[ "$ffvit_remote" != "https://github.com/$1.git" && "$ffvit_remote" != "git@github.com:$1.git" ]]; then
        echo 'Existing origin differs from the requested repository.' >&2
        exit 2
    fi
else
    gh repo create "$1" --"$2" --source=. --remote=origin
fi
# A successful Git push does not replace LFS object upload.
git lfs push --all origin
git push -u origin main
