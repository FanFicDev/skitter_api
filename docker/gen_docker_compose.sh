#!/usr/bin/env bash

cat<<HEAD
version: "3.7"
services:
HEAD

i=0
cat ./config.tsv | tr ',' '\n' | while read -r userf; do
	read -r passf
	read -r host
	read -r pia
	read -r ver
	read -r suff
	host="$(echo "$host" | cut -d'.' -f1)"
	port="$((8191 + i))"
	echo "# ${host} ${pia}"
	#mkdir -p /home/skitter/docker/${host}/m
	{
		cat<<HERE
  ${host}_gluetun:
    image: qmcgaw/gluetun:v3.26.0
    container_name: ${host}_gluetun
    cap_add:
      - NET_ADMIN
    network_mode: bridge
    ports:
      #- 127.0.0.1:8888:8888/tcp # HTTP proxy
      #- 127.0.0.1:8388:8388/tcp # Shadowsocks
      #- 127.0.0.1:8388:8388/udp # Shadowsocks
      #- 127.0.0.1:8000:8000/tcp # Built-in HTTP control server
      - 127.0.0.1:${port}:8191/tcp
    # command:
    volumes:
      - /home/skitter/docker/${host}/m:/gluetun
    secrets:
      - source: ${userf}
        target: openvpn_user
      - source: ${passf}
        target: openvpn_password
    environment:
      # More variables are available, see the readme table
      - VPNSP=private internet access
      - REGION=${pia}
      # Timezone for accurate logs times
      - TZ=UTC
      # disable DNS over TLS
      - DOT=off
    restart: always
  ${host}_flaresolverr${suff}:
    image: ghcr.io/flaresolverr/flaresolverr:${ver}
    container_name: ${host}_flaresolverr${suff}
    environment:
      - LOG_LEVEL=${LOG_LEVEL:-info}
      - LOG_HTML=${LOG_HTML:-false}
      - CAPTCHA_SOLVER=${CAPTCHA_SOLVER:-none}
      - TEST_URL=http://mirror.fanfic.dev/mirror
    network_mode: "service:${host}_gluetun"
    restart: unless-stopped
HERE
	}
	i=$((i + 1))
done

echo ""
echo "secrets:"
cat ./config.tsv | cut -d',' -f1 | sort -u | while read -r userf; do
	echo "  $userf:"
	echo "    file: ./secrets/$userf"
done

cat ./config.tsv | cut -d',' -f2 | sort -u | while read -r passf; do
	echo "  $passf:"
	echo "    file: ./secrets/$passf"
done

