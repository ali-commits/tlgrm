#!/usr/bin/env bash
set -euo pipefail

PY="${PYTHON:-python3}"
F="src/tlgrm/config.py"
A="${TG_API_ID:?}"
B="${TG_API_HASH:?}"

trap 'git checkout -- "$F" 2>/dev/null || true' EXIT

if [ -z "${SETUPTOOLS_SCM_PRETEND_VERSION:-}" ]; then
  if t="$(git describe --tags --exact-match 2>/dev/null)"; then
    export SETUPTOOLS_SCM_PRETEND_VERSION="${t#v}"
  fi
fi

D="$("$PY" - "$A" "$B" <<'PY'
import base64, sys
k = bytes([0x6b, 0x1d, 0x9f, 0x42, 0xa7, 0x33, 0xc8, 0x5e])
p = f"{sys.argv[1]}:{sys.argv[2]}".encode()
print(base64.b64encode(bytes(c ^ k[i % len(k)] for i, c in enumerate(p))).decode())
PY
)"

"$PY" - "$F" "$D" <<'PY'
import re, sys
s = open(sys.argv[1], encoding="utf-8").read()
s, n = re.subn(r'^_q = ""$', f'_q = "{sys.argv[2]}"', s, count=1, flags=re.M)
if n != 1:
    sys.exit("release: marker not found (run from a clean checkout)")
open(sys.argv[1], "w", encoding="utf-8").write(s)
PY

rm -rf dist
"$PY" -m build
ls -1 dist
