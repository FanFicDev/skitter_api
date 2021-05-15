#!/usr/bin/env bash

export OIL_DB_DBNAME=skitter
mkdir -p ./logs/

exec uwsgi --plugin python3 --enable-threads \
	--reuse-port --uwsgi-socket 127.0.0.1:9151 \
	--plugin logfile  \
	--logger file:logfile=./logs/skitter_api.log,maxsize=2000000 \
	--daemonize2 /dev/null \
	--pidfile skitter_api_master.pid \
	--master --processes 2 --threads 3 \
	--manage-script-name --mount /skitter=skitter_api:app

