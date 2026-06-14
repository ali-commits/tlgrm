#!/usr/bin/env bash
#
# Build the tlgrm distribution with the bundled fallback API credentials
# injected at BUILD TIME only.
#
# The credentials are read from the environment (TG_API_ID / TG_API_HASH),
# turned into the obfuscated blob the runtime decoder expects, written into
# src/tlgrm/config.py for the duration of the build, then reverted — so the
# secret never lands in git history. The blob is never printed, so it stays
# out of CI logs too.
#
# Usage:
#   TG_API_ID=1234567 TG_API_HASH=your_hash bash release.sh
#
# Output: built wheel + sdist in dist/.  (Run from a clean checkout.)
set -euo pipefail

PYTHON="${PYTHON:-python3}"
CONFIG="src/tlgrm/config.py"

API_ID="${TG_API_ID:?set TG_API_ID}"
API_HASH="${TG_API_HASH:?set TG_API_HASH}"

# Always restore the committed (empty) placeholder, even on failure.
cleanup() { git checkout -- "$CONFIG" 2>/dev/null || true; }
trap cleanup EXIT

# hatch-vcs derives the version from git; the credential injection below dirties
# the tree, which would otherwise yield a "dev"/local version that PyPI rejects.
# Pin the version to the current tag (the workflow may also set this explicitly).
if [ -z "${SETUPTOOLS_SCM_PRETEND_VERSION:-}" ]; then
  if _tag="$(git describe --tags --exact-match 2>/dev/null)"; then
    export SETUPTOOLS_SCM_PRETEND_VERSION="${_tag#v}"
  fi
fi

# Generate the obfuscated blob (must match the runtime decoder key in config.py).
# Read via argv, print only the blob.
BLOB="$("$PYTHON" - "$API_ID" "$API_HASH" <<'PY'
import base64, sys
api_id, api_hash = sys.argv[1], sys.argv[2]
key = bytes([0x6b, 0x1d, 0x9f, 0x42, 0xa7, 0x33, 0xc8, 0x5e])
p = f"{api_id}:{api_hash}".encode()
print(base64.b64encode(bytes(b ^ key[i % len(key)] for i, b in enumerate(p))).decode())
PY
)"

# Inject into the `_q = ""` placeholder (quietly — never echo $BLOB).
"$PYTHON" - "$CONFIG" "$BLOB" <<'PY'
import re, sys
path, blob = sys.argv[1], sys.argv[2]
src = open(path, encoding="utf-8").read()
new, n = re.subn(r'^_q = ""$', f'_q = "{blob}"', src, count=1, flags=re.M)
if n != 1:
    sys.exit("release.sh: could not find the `_q = \"\"` placeholder to inject "
             "(run from a clean checkout)")
open(path, "w", encoding="utf-8").write(new)
PY

echo ">> Injected bundled credentials into $CONFIG (not echoed). Building..."
rm -rf dist
"$PYTHON" -m build

echo ">> Build complete. Artifacts:"
ls -1 dist
echo ">> $CONFIG will be reverted to the committed placeholder on exit."
