#!/bin/zsh
set -e

cd -- "$(dirname -- "$0")"

entry_url="http://127.0.0.1:8765/segmentation_lab.html"
if curl --silent --fail --max-time 1 "$entry_url" >/dev/null 2>&1; then
  open "$entry_url"
  exit 0
fi

if [[ -x ".venv-open-vocab/bin/python" ]]; then
  workflow_python=".venv-open-vocab/bin/python"
elif [[ -x ".venv-sam/bin/python" ]]; then
  workflow_python=".venv-sam/bin/python"
else
  workflow_python="python3"
fi

"$workflow_python" workflow_server.py --host 127.0.0.1 --port 8765 &
workflow_server_pid=$!
trap 'kill "$workflow_server_pid" 2>/dev/null || true' EXIT INT TERM

sleep 1
open "$entry_url"
wait "$workflow_server_pid"
