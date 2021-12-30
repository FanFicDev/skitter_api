from typing import (
		Any, Dict, Union, Tuple, Optional, Generator, List,
		Callable, Iterable
	)
import os
import os.path
import time
import traceback
import threading
from enum import IntEnum
from flask import Flask, Response, request, render_template, \
	make_response
from flask.typing import ResponseReturnValue
import werkzeug.wrappers
from werkzeug.datastructures import Headers
from werkzeug.exceptions import HTTPException, NotFound
from oil import oil
from weaver import Web, RemoteWebScraper
from priv import API_KEYS, NODE_NAME

app = Flask(__name__, static_url_path='')
defaultRequestTimeout = 60

CACHE_BUSTER=1

@app.errorhandler(Exception)
def page_not_found(error: Exception) -> ResponseReturnValue:
	if isinstance(error, NotFound):
		return make_response({'err':404,'msg':'not found'}, 404)
	print(f'page_not_found: {error}')
	traceback.print_exc()
	return make_response({'err':500,'msg':'internal server error'}, 500)

@app.route('/')
def index() -> ResponseReturnValue:
	return make_response(render_template('index.html', CACHE_BUSTER=CACHE_BUSTER))

@app.route('/v0', methods=['GET'], strict_slashes=False)
@app.route('/v0/status', methods=['GET'])
def v0_status() -> ResponseReturnValue:
	return make_response({'err':0,'status':'ok',
		'pid':os.getpid(),'tident':threading.get_ident(),})

def make_response_web(w: Optional[Web]) -> ResponseReturnValue:
	if w is None or w.response is None or w.created is None:
		return page_not_found(NotFound())
	fres = make_response(w.response)
	fres.headers['X-Weaver-Id'] = str(w.id) + '_' + NODE_NAME
	fres.headers['X-Weaver-Created'] = str(int(w.created//1000))
	fres.headers['X-Weaver-Url'] = str(w.url)
	return fres

def get_request_value(key: str, dflt: Optional[str]) -> Optional[str]:
	val = request.form.get(key, None)
	if val is None:
		val = request.args.get(key, None)
	if val is None:
		val = dflt
	return val

@app.route('/v0/cache', methods=['GET'])
def v0_cache() -> ResponseReturnValue:
	apiKey = get_request_value('apiKey', '')
	if apiKey not in API_KEYS:
		return make_response({'err':-401,'msg':'unauthorized'}, 401)

	q = get_request_value('q', None)
	u = get_request_value('u', None)
	print(f'v0_cache: {q=}, {u=}')
	if (q is None or len(q.strip()) < 1) \
			and (u is None or len(u.strip()) < 1):
		print(f'v0_cache: q and u are empty')
		return page_not_found(NotFound())

	latest = None
	db = oil.open()
	if u:
		latest = Web.latest(db, ulike=u, status=200)
	else:
		latest = Web.latest(db, q, status=200)

	if latest is None or latest.response is None or latest.created is None:
		print(f'v0_cache: {q=}, {u=}: not found')
	else:
		print(f'v0_cache: {q=}, {u=}: found: len: {len(latest.response)}, url: {latest.url}, id: {latest.id}, created: {latest.created}')
	return make_response_web(latest)

@app.route('/v0/crawl', methods=['GET'])
def v0_crawl() -> ResponseReturnValue:
	apiKey = get_request_value('apiKey', '')
	if apiKey not in API_KEYS:
		return make_response({'err':-401,'msg':'unauthorized'}, 401)

	q = get_request_value('q', None)
	print(f'v0_crawl: {q=}')
	if (q is None or len(q.strip()) < 1):
		return page_not_found(NotFound())

	if not q.startswith('http://') and not q.startswith('https://'):
		return page_not_found(NotFound())

	ts = int(time.time()) - 1
	db = oil.open()
	scraper = RemoteWebScraper(db)
	scraper.scrape(q)
	latest = Web.latest(db, q, status=200)
	if latest is None or latest.created is None:
		print(f'v0_crawl: {q=}: error: no latest entry')
		return make_response({'err':-500,'msg':'internal server error'}, 500)
	lts = int(latest.created//1000)
	if lts < ts:
		print(f'v0_crawl: {q=}: error getting fresh crawl: {ts} >= {lts}')
		return make_response({'err':-500,'msg':'internal server error'}, 500)
	return make_response_web(latest)

if __name__ == '__main__':
	app.run(debug=True)

