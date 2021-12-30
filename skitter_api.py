from typing import (
		Any, Dict, Union, Tuple, Optional, Generator, List,
		Callable, Iterable
	)
import os
import os.path
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

@app.route('/v0/cache', methods=['GET'])
def v0_cache() -> ResponseReturnValue:
	apiKey = request.values.get('apiKey', '')
	if apiKey not in API_KEYS:
		return make_response({'err':-401,'msg':'unauthorized'}, 401)

	q = request.values.get('q', None)
	u = request.values.get('u', None)
	print(f'v0_cache: {q=}, {u=}')
	if (q is None or len(q.strip()) < 1) \
			and (u is None or len(u.strip()) < 1):
		return page_not_found(NotFound())

	latest = None
	with oil.open() as db:
		if u:
			latest = Web.latest(db, ulike=u, status=200)
		else:
			latest = Web.latest(db, q, status=200)

	if latest is None or latest.response is None or latest.created is None:
		print(f'v0_cache: {q=}, {u=}: not found')
		return page_not_found(NotFound())
	print(f'v0_cache: {q=}, {u=}: found: len: {len(latest.response)}, url: {latest.url}, id: {latest.id}, created: {latest.created}')
	fres = make_response(latest.response)
	fres.headers['X-Weaver-Id'] = str(latest.id) + '_' + NODE_NAME
	fres.headers['X-Weaver-Created'] = str(int(latest.created//1000))
	fres.headers['X-Weaver-Url'] = str(latest.url)
	return fres

@app.route('/v0/crawl', methods=['GET'])
def v0_crawl() -> ResponseReturnValue:
	apiKey = request.values.get('apiKey', '')
	if apiKey not in API_KEYS:
		return make_response({'err':-401,'msg':'unauthorized'}, 401)

	q = request.values.get('q', None)
	print(f'v0_crawl: {q=}')
	if (q is None or len(q.strip()) < 1):
		return page_not_found(NotFound())

	if not q.startswith('http://') and not q.startswith('https://'):
		return page_not_found(NotFound())

	with oil.open() as db:
		scraper = RemoteWebScraper(db)
		scraper.scrape(q)

	return v0_cache()

if __name__ == '__main__':
	app.run(debug=True)

