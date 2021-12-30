#!/usr/bin/env bash
set -e

if [[ ! -f priv.py ]]; then
	echo "err: priv.py does not exist"
	exit 1
fi

target="${1-skitter}"
echo "pushing to host: $target"

mypy skitter_worker.py skitter_story_worker.py skitter_api.py

rsync -aPv --exclude venv ../skitter_api/ skitter@${target}:skitter_api
rsync -aPv ../python-oil ../python-weaver skitter@${target}:
rsync -aPv --no-owner --no-group ./etc/ root@${target}:/etc/
rsync -aPv --no-owner --no-group ./var/ root@${target}:/var/

ssh skitter@${target} './skitter_api/setup_skitter_env.sh'

