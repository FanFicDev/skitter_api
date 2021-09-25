#!/usr/bin/env python3
from typing import TYPE_CHECKING, Optional, List, Tuple, Dict, cast
if TYPE_CHECKING:
	import psycopg2
import base64
import json
import sys
import subprocess
import time
import traceback
import random
import urllib.parse
import requests
from oil import oil
import oil.util as util
from weaver import WebSource, Encoding, Web, WebQueue
import weaver.enc as enc
from priv import LOOKUP_REMOTE_ENDPOINT

defaultRequestTimeout = 60
defaultUserAgent = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36'
logFileName = 'skitter_worker.log'

publicIp = ''

blockSize = 50

def plog(msg: str) -> None:
	print(msg)
	global logFileName
	util.logMessage(msg, fname=logFileName, logDir='./')

def get_node_name(workerId: int) -> str:
	return f'fr{workerId}a'

def get_node_host(workerId: int) -> str:
	return 'localhost:' + str(8191 + workerId)

def run_command(cmd: List[str], timeout: float = 5
		) -> Tuple[bytes, bytes]:
	p = subprocess.Popen(cmd,
			stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	stdout, stderr = p.communicate(timeout=timeout)
	ret = p.poll()
	if ret != 0:
		raise Exception(f'run_command: ret != 0: {ret}')
	return stdout, stderr

def get_public_ip() -> str:
	out, _ = run_command(['curl', '-f', '-m', '7', '-s', LOOKUP_REMOTE_ENDPOINT],
			timeout=10)
	return out.decode('utf-8').strip()

def run_command_in_container(container: str, cmd: str, timeout: float = 5
		) -> Tuple[bytes, bytes]:
	return run_command([
			'docker', 'exec', '-it', container,
			'/bin/sh', '-c', cmd
		], timeout)

def get_worker_ip(node: str) -> str:
	out, _ = run_command_in_container(f'{node}_gluetun',
			f'curl -f -m 10 -s {LOOKUP_REMOTE_ENDPOINT}', timeout=15)
	return out.decode('utf-8').strip()

def restart_worker_vpn(node: str) -> None:
	plog(f'restart_worker_vpn: restarting {node}_gluetun')
	run_command(['docker', 'restart', f'{node}_gluetun'], timeout=60)
	time.sleep(30)

def restart_worker_fr(node: str) -> None:
	plog(f'restart_worker_fr: restarting {node}_flaresolverr')
	run_command(['docker', 'restart', f'{node}_flaresolverr'], timeout=60)
	time.sleep(30)

def get_fr_ok(workerId: int) -> bool:
	global defaultRequestTimeout
	host = get_node_host(workerId)
	r = requests.post(f'http://{host}', timeout=defaultRequestTimeout)
	if r.status_code != 200:
		return False
	try:
		ro = r.json()
		return str(ro['status']) == 'ok'
	except:
		pass
	return False

def get_sessions_list(workerId: int) -> List[str]:
	global defaultRequestTimeout
	host = get_node_host(workerId)
	r = requests.post(f'http://{host}/v1', timeout=defaultRequestTimeout,
			json={'cmd':'sessions.list'})
	if r.status_code != 200:
		raise Exception(f'get_sessions_list: status != 200: {r.status_code}')
	ro = r.json()
	return cast(List[str], ro['sessions'])

def create_session(workerId: int, sessionName: str, userAgent: str) -> bool:
	global defaultRequestTimeout
	host = get_node_host(workerId)
	r = requests.post(f'http://{host}/v1', timeout=defaultRequestTimeout,
			json={'cmd':'sessions.create','userAgent':userAgent,'session':sessionName})
	if r.status_code != 200:
		raise Exception(f'create_session: status != 200: {r.status_code}')
	return sessionName in get_sessions_list(workerId)

class FlareSolverrResponse:
	def __init__(self, status: int, response: bytes):
		self.status = status
		self.response = response
		# requestHeaders, responseHeaders?

def make_req(workerId: int, url: str, headers: Optional[Dict[str, str]] = None,
		download: bool = True
		) -> FlareSolverrResponse:
	global defaultRequestTimeout
	host = get_node_host(workerId)
	data = {'cmd':'request.get','session':'skitter','download':download,'url':url}
	if headers is not None:
		data['headers'] = headers
	r = requests.post(f'http://{host}/v1', timeout=defaultRequestTimeout,
			json=data)
	if r.status_code != 200:
		raise Exception(f'make_req: {url=}: fr status != 200: {r.status_code}')
	ro = r.json()
	if 'solution' not in ro:
		raise Exception(f'make_req: {url=}: no solution')
	if 'status' not in ro['solution']:
		raise Exception(f'make_req: {url=}: no solution.status')
	if 'response' not in ro['solution']:
		raise Exception(f'make_req: {url=}: no solution.response')

	status = int(ro['solution']['status'])
	res = ro['solution']['response']
	if download:
		res = base64.b64decode(res)
	if isinstance(res, str):
		res = res.encode('utf-8')
	return FlareSolverrResponse(status, res)

def get_worker_ip_fr(workerId: int) -> str:
	r = make_req(workerId, LOOKUP_REMOTE_ENDPOINT)
	if r.status != 200:
		raise Exception('failed to determine remote address')
	return r.response.decode('utf-8').strip()

def extractTitle(html: str) -> str:
	bidx = html.find('<title>')
	eidx = -1
	if bidx >= 0:
		eidx = html.find('</title>', bidx)
	if eidx >= 0:
		return html[bidx + len('<title>'):eidx]

	from bs4 import BeautifulSoup # type: ignore
	soup = BeautifulSoup(html, 'html5lib')
	title = soup.find('title')
	if title is None:
		raise Exception('extractTitle: unable to find title')
	return str(title.get_text())

def scrape(db: 'psycopg2.connection', source: WebSource, workerId: int,
		url: str, triesLeft: int = 3) -> Web:
	if triesLeft <= 0:
		raise Exception('scrape: exceeded retry count')

	created = int(time.time() * 1000)
	r = make_req(workerId, url)

	w = Web(created_=created, url_=url, status_=r.status, sourceId_=source.id)
	w.response = r.response
	w.requestHeaders = None # str(r.request.headers).encode('utf-8')
	w.responseHeaders = None # str(r.headers).encode('utf-8')

	if w.status == 200:
		dec = enc.decode(w.response, url)
		if dec is not None and dec[0] is not None:
			w.encoding = Encoding.lookup(db, dec[0]).id

		if dec is not None and dec[1] is not None:
			title = ''
			try:
				title = extractTitle(dec[1]).strip()
			except:
				pass
			if title == 'Just a moment...' \
					or title == 'Attention Required! | Cloudflare':
				plog(f'scrape: got 200 status CF page, retrying: {triesLeft - 1}')
				time.sleep(6 + random.random() * 2)
				return scrape(db, source, workerId, url, triesLeft - 1)

	w.save(db)
	return w

def workBlock(db: 'psycopg2.connection', workerId: int, stripeCount: int,
		stripe: int, cnt: int, source: WebSource) -> None:
	defaultTimeout = 600.0
	idleTimeout = 0.25
	timeout = defaultTimeout
	while cnt > 0 and timeout > 0:
		wq = WebQueue.next(db, workerId, stripeCount=stripeCount, stripe=stripe)
		if wq is None:
			timeout -= idleTimeout
			time.sleep(idleTimeout)
			continue
		assert(wq.url is not None)
		plog(f'workBlock: {cnt}: {wq.url}')
		cnt -= 1
		timeout = defaultTimeout
		w = scrape(db, source, workerId, wq.url)
		wq.dequeue(db)
		rlen = -1 if w.response is None else len(w.response)
		plog(f'workBlock:   status {w.status}, {rlen} bytes')

		time.sleep(6 + random.random() * 2)

def maybe_restart_vpn(node: str) -> bool:
	try:
		rip = get_worker_ip(node)
		return False
	except:
		pass

	restart_worker_vpn(node)
	return True

def try_reset(workerId: int) -> bool:
	try:
		node = get_node_name(workerId)
		restart_worker_vpn(node)
		restart_worker_fr(node)
		return True
	except Exception as e:
		plog(f'try_reset: exception:\n{e}\n{traceback.format_exc()}')
	return False

def work(db: 'psycopg2.connection', workerId: int,
		stripeCount: int, stripe: int, blockSize: int) -> int:
	node = get_node_name(workerId)
	while True:
		if maybe_restart_vpn(node):
			plog('work: restarted vpn; restarting fr')
			restart_worker_fr(node)

		if not get_fr_ok(workerId):
			plog('work: fr is not ok; attempting to restart fr')
			restart_worker_fr(node)
			if not get_fr_ok(workerId):
				plog('work: fr still not ok; aborting')
				return 2

		if 'skitter' not in get_sessions_list(workerId):
			global defaultUserAgent
			plog('work: skitter not in sessions list; trying to create it...')
			create_session(workerId, 'skitter', defaultUserAgent)

		if 'skitter' not in get_sessions_list(workerId):
			plog('work: skitter session does not exist; aborting')
			return 3

		remoteIP = get_worker_ip_fr(workerId)
		plog(f'work: {remoteIP=}')
		source = WebSource.lookup(db, node, remoteIP)
		plog(f'work: source: {source.__dict__}')
		if source.isLocal() or source.source is None \
				or source.source.startswith(publicIp):
			plog('work: source is local; aborting')
			return 1

		WebQueue.resetWorker(db, workerId)
		workBlock(db, workerId, stripeCount, stripe, blockSize, source)

def main(args: List[str]) -> int:
	global logFileName
	stripeCount = 1
	stripe = 0
	workerId = int(sys.argv[1])
	logFileName = f'skitter_worker_{workerId}.log'

	global publicIp
	publicIp = get_public_ip()
	plog(f'main: public ip: {publicIp}')

	global blockSize

	run = True
	while run:
		doTryReset = False
		try:
			with oil.open() as db:
				work(db, workerId, stripeCount, stripe, blockSize)
		except KeyboardInterrupt:
			run = False
		except Exception as e:
			plog(f'work: exception:\n{e}\n{traceback.format_exc()}')
			doTryReset = True

		try:
			WebQueue.resetWorker(db, workerId)
		except KeyboardInterrupt:
			run = False
		except:
			pass

		if doTryReset:
			plog('main: sleeping then reseting worker')
			time.sleep(30 + random.random() * 30)
			try_reset(workerId)

		if run:
			plog('main: sleeping then restarting work loop')
			time.sleep(60 + random.random() * 90)

	return 0

if __name__ == '__main__':
	try:
		main(sys.argv)
	except KeyboardInterrupt:
		pass

