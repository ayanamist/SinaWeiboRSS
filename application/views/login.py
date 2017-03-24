# -*- coding: utf-8 -*-
from __future__ import absolute_import

import json
import logging
import urllib
import urlparse

from google.appengine.api import urlfetch

from application import views
from application.utils import crypto


class Login(views.BaseHandler):
    def get(self):
        flash_messages = []
        code = self.request.GET.get("code")
        if code is not None:
            r = urlfetch.fetch("https://api.weibo.com/oauth2/access_token?" + urllib.urlencode({
                "client_id": self.app.config["CONSUMER_KEY"],
                "client_secret": self.app.config["CONSUMER_SECRET"],
                "grant_type": "authorization_code",
                "redirect_uri": urlparse.urljoin("https://" + self.request.host, self.uri_for("login")),
                "code": code,
            }), method=urlfetch.POST)
            resp = json.loads(r.content)
            if "error" in resp:
                flash_messages.append(u"错误：%s" % resp["error"])
            else:
                logging.debug("access_token: %s" % resp)
                sid = crypto.encrypt(resp["access_token"], self.app.config["SECRET_KEY"])
                rss_url = urlparse.urljoin("https://" + self.request.host, self.uri_for("rss", sid=sid))
                self.render_response("rss.html", rss_url=rss_url)
                return
        self.render_response("login.html", flash_messages=flash_messages)

    def post(self):
        authorize_url = "https://api.weibo.com/oauth2/authorize?" + urllib.urlencode({
            "client_id": self.app.config["CONSUMER_KEY"],
            "response_type": "code",
            "redirect_uri": urlparse.urljoin("https://" + self.request.host, self.uri_for("login")),
        })
        self.redirect(authorize_url)
