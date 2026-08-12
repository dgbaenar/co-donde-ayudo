#!/usr/bin/env bash
# Validates a git commit message against Conventional Commits format.
# Usage: ./validate.sh                     # validates HEAD commit
#        ./validate.sh "feat: add thing"   # validates provided string
#        ./validate.sh --staged            # validates staged commit msg file

set -euo pipefail

SUBJECT=""
MODE="head"

if [[ "${1:-}" == "--staged" ]]; then
  MODE="staged"
elif [[ -n "${1:-}" ]]; then
  SUBJECT="$1"
  MODE="arg"
fi

# Fetch the subject line
if [[ "$MODE" == "head" ]]; then
  SUBJECT=$(git log -1 --format="%s")
elif [[ "$MODE" == "staged" ]]; then
  MSG_FILE=$(git rev-parse --git-dir)/COMMIT_EDITMSG
  if [[ ! -f "$MSG_FILE" ]]; then
    echo "ERROR: No staged commit message found at $MSG_FILE" >&2
    exit 1
  fi
  SUBJECT=$(head -1 "$MSG_FILE")
fi

ERRORS=()

# Rule: valid Conventional Commit type
VALID_TYPES="feat|fix|refactor|docs|test|build|chore|style|perf|revert"
if ! echo "$SUBJECT" | grep -qE "^($VALID_TYPES)(\([^)]+\))?!?: .+"; then
  ERRORS+=("Subject must start with a valid type ($VALID_TYPES) followed by a colon and space.")
fi

# Rule: subject ≤ 72 characters
SUBJECT_LEN=${#SUBJECT}
if (( SUBJECT_LEN > 72 )); then
  ERRORS+=("Subject is $SUBJECT_LEN characters. Maximum is 72.")
fi

# Rule: no period at end of subject
if echo "$SUBJECT" | grep -qE '\.$'; then
  ERRORS+=("Subject must not end with a period.")
fi

# Rule: no uppercase after the colon+space
AFTER_COLON=$(echo "$SUBJECT" | sed -E 's/^[^:]+: //')
if echo "$AFTER_COLON" | grep -qE '^[A-Z]'; then
  ERRORS+=("Subject text after ': ' must start with a lowercase letter.")
fi

# Rule: imperative mood check (heuristic — flags common past-tense endings)
if echo "$AFTER_COLON" | grep -qiE '^(added|fixed|removed|updated|changed|implemented|refactored)'; then
  ERRORS+=("Subject appears to use past tense. Use imperative mood ('add', 'fix', 'remove').")
fi

# Report
if (( ${#ERRORS[@]} == 0 )); then
  echo "OK: commit message is valid."
  echo "    Subject: $SUBJECT"
  exit 0
else
  echo "FAIL: commit message has ${#ERRORS[@]} issue(s)."
  echo "      Subject: $SUBJECT"
  for err in "${ERRORS[@]}"; do
    echo "  - $err"
  done
  exit 1
fi
