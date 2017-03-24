from __future__ import absolute_import

import json
import logging
import urllib
import zlib

from google.appengine.api import memcache
from google.appengine.api import urlfetch

from application import views
from application.utils import crypto


class RSS(views.BaseHandler):
    def get(self, sid):
        results = memcache.get(sid)
        if results:
            try:
                results = json.loads(zlib.decompress(results))["statuses"]
            except Exception:
                pass
        if not results:
            try:
                access_token = crypto.decrypt(sid, self.app.config["SECRET_KEY"])
            except (ValueError, TypeError):
                self.response.status_int = 403
                return

            logging.debug("access_token: %s", access_token)
            resp = urlfetch.fetch("https://api.weibo.com/2/statuses/home_timeline.json?" + urllib.urlencode({
                "count": 100,
                "base_app": 0,
                "feature": 0,
                "trim_user": 0,
            }), headers={"Authorization": "OAuth2 " + access_token})
            if resp.status_code != 200:
                logging.error("status_code %d, content: %s", resp.status_code, resp.content)
                self.response.status_int = 500
                self.response.write(resp.content)
                return
            body = json.loads(resp.content)
            if "error" in body:
                logging.error("error: %s", resp.content)
                self.response.status_int = 500
                self.response.write(body["error"])
                return
            memcache.set(sid, zlib.compress(json.dumps(resp.content), 9), time=120)
            results = body["statuses"]
            for item in results:
                logging.debug(json.dumps(item))
        self.response.headers["Content-Type"] = "application/rss+xml; charset=utf-8"
        self.render_response("rss.xml", results=results)
