#!/bin/sh
set -eu

input=${1:-}
if [ -z "$input" ]; then
  echo "usage: validate.sh <message-file-or-subject>" >&2
  exit 2
fi

if [ -f "$input" ]; then
  message=$(sed -n '1p' "$input")
  grep -n '[[:space:]]$' "$input" >/dev/null && {
    echo "trailing whitespace found" >&2
    exit 1
  }
  grep -En '<[^>]+>|TODO|TBD' "$input" >/dev/null && {
    echo "placeholder found" >&2
    exit 1
  }
else
  message=$input
fi

[ "${#message}" -le 72 ] || { echo "subject exceeds 72 characters" >&2; exit 1; }
printf '%s\n' "$message" | grep -Eq '^(feat|fix|docs|test|refactor|chore|build|ci)(\([a-z0-9._/-]+\))?!?: .+' || {
  echo "subject is not a Conventional Commit" >&2
  exit 1
}
echo "git message: PASS"
