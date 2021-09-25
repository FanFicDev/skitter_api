from typing import Any, Dict, Union, Tuple, Optional, cast
import os
import os.path
import threading
from enum import IntEnum
from flask import Flask, Response, request, render_template, \
	make_response
import werkzeug.wrappers
from werkzeug.exceptions import HTTPException, NotFound
from oil import oil
from weaver import Web, RemoteWebScraper
from priv import API_KEYS

app = Flask(__name__, static_url_path='')
defaultRequestTimeout = 60

BasicFlaskResponse = Union[Response, werkzeug.wrappers.Response, str, Dict[str, Any]]
FlaskResponse = Union[BasicFlaskResponse, Tuple[BasicFlaskResponse, int]]

CACHE_BUSTER=1

class WebError(IntEnum):
	success = 0
	no_query = -1

errorMessages = {
		WebError.success: 'success',
		WebError.no_query: 'no query',
	}

def getErr(err: WebError, extra: Optional[Dict[str, Any]] = None
		) -> Dict[str, Any]:
	base = {'err':int(err),'msg':errorMessages[err]}
	if extra is not None:
		base.update(extra)
	return base

@app.errorhandler(404)
def page_not_found(e: HTTPException) -> FlaskResponse:
	return make_response({'err':404,'msg':'not found'}, 404)

@app.route('/')
def index() -> FlaskResponse:
	return render_template('index.html', CACHE_BUSTER=CACHE_BUSTER)

@app.route('/v0', methods=['GET'], strict_slashes=False)
@app.route('/v0/status', methods=['GET'])
def v0_status() -> FlaskResponse:
	return make_response({'err':0,'status':'ok',
		'pid':os.getpid(),'tident':threading.get_ident(),})

@app.route('/v0/cache', methods=['GET'])
def v0_cache() -> FlaskResponse:
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
	fres.headers['X-Weaver-Id'] = str(latest.id) + '_athena'
	fres.headers['X-Weaver-Created'] = str(int(latest.created//1000))
	fres.headers['X-Weaver-Url'] = str(latest.url)
	return fres

@app.route('/v0/crawl', methods=['GET'])
def v0_crawl() -> FlaskResponse:
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

