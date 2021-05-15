#!/usr/bin/env bash

kill -s SIGINT $(cat skitter_api_master.pid)
rm skitter_api_master.pid

