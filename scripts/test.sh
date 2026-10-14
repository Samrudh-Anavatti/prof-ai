#!/usr/bin/env bash
# Runs the full regression suite. Update as the stack lands.
set -euo pipefail
cd "$(dirname "$0")/.."

python=python
for candidate in .venv/bin/python .venv/Scripts/python.exe; do
  [ -x "$candidate" ] && python=$candidate && break
done

ran=0
if find tests -name 'test_*.py' -print -quit | grep -q .; then
  "$python" -m pytest -q tests
  ran=1
fi
while IFS= read -r pkg; do
  (cd "$(dirname "$pkg")" && npm test --silent)
  ran=1
done < <(find . -name package.json -not -path '*/node_modules/*')

if [ "$ran" -eq 0 ]; then
  echo "No tests yet."
fi
