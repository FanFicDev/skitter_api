skitter_api is a small wrapper around a set of FlareSolverr [^1] instances for load
balancing and redundancy purposes. Essentially a series of docker containers
comprised of gluetun[^2] providing a VPN connection and FlareSolverr providing CF
workarounds are kept alive and proxied to.

Currently these workers choose from a shared queue table stored in postgres;
this is for ease-of-adapting from a previous project that was trivially
shardable. This is far from ideal for a number of reasons. There's an initial
effort to move to rabbitmq queues instead.

Ensure you create a valid `etc/nginx/auth/skitter.htpasswd` file.

`/etc/hosts` on the deploy target should contain an entry for polaris.fanfic.dev

Create the docker container `docker/config.tsv`; see `docker/config.ex.tsv` for an
example. 

The general format is:	
```csv
user_secret_name,pass_secret_name,subdomain,region
```

Create the secret files referenced by the config, for example:
- `./docker/secrets/openvpn_user`
- `./docker/secrets/openvpn_password`

these should be single line files

Regenerate the docker-compose.yml file:
```sh
docker/
./gen_docker_compose.sh > ./docker-compose.yml
```

This depends on the same sql that python-weaver[^3] does.

Copy `priv.ex.py` to `priv.py`, generate a random api key, and optionally set a
`NODE_NAME`.


Setup the virtualenv to manage dependencies:
```sh
python -m virtualenv ./venv
./venv/bin/python -m pip install --upgrade pip
./venv/bin/python -m pip install -r requirements.txt
```

[^1]: https://github.com/FlareSolverr/FlareSolverr
[^2]: https://github.com/qdm12/gluetun
[^3]: https://github.com/FanFicDev/python-weaver
