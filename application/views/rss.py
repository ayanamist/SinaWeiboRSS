from __future__ import absolute_import

import logging

from application import views
from application.models import weibo
from application.utils import crypto


class RSS(views.BaseHandler):
    def get(self, sid):
        try:
            plaintext_sid = crypto.decrypt(sid, self.app.config["SECRET_KEY"])
            oauth_token, oauth_token_secret = plaintext_sid.split(":", 1)
        except (ValueError, TypeError):
            self.response.status_int = 403
            return
        api = weibo.API(self.app.config["CONSUMER_KEY"], self.app.config["CONSUMER_SECRET"])
        api.bind_auth(oauth_token, oauth_token_secret)
        params = {
            "count": 100,
            "base_app": 0,
            "feature": 0,
        }
        try:
            result = api.get("statuses/home_timeline", version="", **params).json()
        except weibo.Error as e:
            logging.exception(str(e))
            self.response.status_int = 500
            return
        self.response.headers["Content-Type"] = "application/rss+xml; charset=utf-8"
        logging.debug(result)