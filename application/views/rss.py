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
                results = json.loads(zlib.decompress(results))
            except Exception:
                results = None
        if not results:
            try:
                access_token = crypto.decrypt(sid, self.app.config["SECRET_KEY"])
            except (ValueError, TypeError):
                self.response.status_int = 403
                return

            logging.debug("access_token: %s", access_token)
            r = urlfetch.fetch("https://api.weibo.com/2/statuses/home_timeline.json?" + urllib.urlencode({
                "count": 100,
                "base_app": 0,
                "feature": 0,
                "trim_user": 0,
            }), headers={"Authorization": "OAuth2 " + access_token})
            content = r.content
            body = json.loads(content)
            if "error" in body:
                logging.error("error: %s", content)
                self.response.status_int = 500
                self.response.write(body["error"])
                return
            results = body["statuses"]
            long_text_ids = []
            long_text_map = dict()
            for status in results:
                if status["isLongText"]:
                    long_text_ids.append(status["idstr"])
            if len(long_text_ids) > 0:
                ids = ",".join(long_text_ids)
                r = urlfetch.fetch("https://api.weibo.com/2/statuses/show_batch.json?" + urllib.urlencode({
                    "ids": ids,
                    "isGetLongText": "1",
                }), headers={"Authorization": "OAuth2 " + access_token})
                body = json.loads(r.content)
                if "error" in body:
                    logging.warn("show_batch %s error: %s", ids, str(body["error"]))
                elif "statuses" in body:
                    for status in body["statuses"]:
                        if "longText" in status:
                            long_text_map[status["idstr"]] = status["longText"]["longTextContent"]
            for status in results:
                if status["isLongText"]:
                    text = long_text_map.get(status["idstr"])
                    if text is not None:
                        logging.debug("replace long text for %s: %s", status["idstr"], text)
                        status["text"] = text
                        status["isLongText"] = False
            memcache.set(sid, zlib.compress(json.dumps(results), 9), time=120)
        self.response.headers["Content-Type"] = "application/rss+xml; charset=utf-8"
        self.render_response("rss.xml", results=results)
