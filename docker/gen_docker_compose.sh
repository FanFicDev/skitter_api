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
	host="$(echo "$host" | cut -d'.' -f1)"
	port="$((8191 + i))"
	echo "# ${host} ${pia}"
	#mkdir -p /home/skitter/docker/${host}/m
	{
		cat<<HERE
  REPHOST_gluetun:
    image: qmcgaw/gluetun
    container_name: REPHOST_gluetun
    cap_add:
      - NET_ADMIN
    network_mode: bridge
    ports:
      #- 127.0.0.1:8888:8888/tcp # HTTP proxy
      #- 127.0.0.1:8388:8388/tcp # Shadowsocks
      #- 127.0.0.1:8388:8388/udp # Shadowsocks
      #- 127.0.0.1:8000:8000/tcp # Built-in HTTP control server
      - 127.0.0.1:REPPORT:8191/tcp
    # command:
    volumes:
      - /home/skitter/docker/REPHOST/m:/gluetun
    secrets:
      - source: REPUSER
        target: openvpn_user
      - source: REPPASS
        target: openvpn_password
    environment:
      # More variables are available, see the readme table
      - VPNSP=private internet access
      - REGION=REPPIA
      # Timezone for accurate logs times
      - TZ=
    restart: always
  REPHOST_flaresolverr:
    # DockerHub mirror flaresolverr/flaresolverr:latest
    image: ghcr.io/flaresolverr/flaresolverr:latest
    container_name: REPHOST_flaresolverr
    environment:
      - LOG_LEVEL=${LOG_LEVEL:-info}
      - LOG_HTML=${LOG_HTML:-false}
      - CAPTCHA_SOLVER=${CAPTCHA_SOLVER:-none}
    network_mode: "service:REPHOST_gluetun"
    restart: unless-stopped
HERE
	} | sed -e "s/REPHOST/${host}/g" -e "s/REPPORT/${port}/g" \
		-e "s/REPPIA/${pia}/g" \
		-e "s/REPUSER/${userf}/g" -e "s/REPPASS/${passf}/g"
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

