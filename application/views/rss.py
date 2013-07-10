from __future__ import absolute_import

import json
import logging
import zlib

try:
    from google.appengine.api import memcache
    from google.appengine.api import urlfetch
except ImportError:
    memcache = None
    urlfetch = None

from application import views
from application.models import weibo
from application.utils import crypto


class RSS(views.BaseHandler):
    def get(self, sid):
        if memcache:
            results = memcache.get(sid)
        else:
            results = None
        if results:
            try:
                results = json.loads(zlib.decompress(results))
            except (ValueError, TypeError):
                pass
        if not results:
            try:
                plaintext_sid = crypto.decrypt(sid, self.app.config["SECRET_KEY"])
                oauth_token, oauth_token_secret = plaintext_sid.split(":", 1)
            except (ValueError, TypeError):
                self.response.status_int = 403
                return

            # Visit API endpoint directly via urlfetch.fetch to make subsequent request successful.
            # It's maybe a GAE bug.
            rpc = None
            if urlfetch:
                rpc = urlfetch.create_rpc()
                urlfetch.make_fetch_call(rpc, "%s/statuses/home_timeline.json" % weibo.BASE_URL,
                                         follow_redirects=False)

            api = weibo.API(self.app.config["CONSUMER_KEY"], self.app.config["CONSUMER_SECRET"])
            api.bind_auth(oauth_token, oauth_token_secret)
            params = {
                "count": 100,
                "base_app": 0,
                "feature": 0,
            }
            try:
                results = api.get("statuses/home_timeline", version="", **params).json()
            except weibo.Error:
                logging.exception("API Timeout")
                self.response.status_int = 502
                self.response.write("API Timeout")
                return
            finally:
                if rpc:
                    try:
                        rpc.get_result()
                    except urlfetch.Error as e:
                        logging.debug("Fake request failed: %s" % str(e))
            if memcache:
                memcache.set(sid, zlib.compress(json.dumps(results), 9), time=120)
        self.response.headers["Content-Type"] = "application/rss+xml; charset=utf-8"
        self.render_response("rss.xml", results=results)

