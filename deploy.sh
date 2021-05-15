#!/usr/bin/env bash
set -e

mypy skitter_worker.py skitter_api.py

rsync -aPv ../skitter_api/ skitter:skitter_api
rsync -aPv ../python-oil ../python-weaver skitter:
rsync -aPv --no-owner --no-group ./etc/ root@skitter:/etc/

ssh skitter './skitter_api/setup_skitter_env.sh'

