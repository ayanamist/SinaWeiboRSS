# -*- coding: utf-8 -*-
from __future__ import absolute_import

import urlparse

from application import views
from application.models import weibo
from application.utils import crypto


class Login(views.BaseHandler):
    def get(self):
        self.render_response("login.html")

    def post(self):
        flash_messages = []
        username = self.request.POST.get("username")
        password = self.request.POST.get("password")
        if username and password:
            params = {
                "x_auth_mode": "client_auth",
                "x_auth_username": username,
                "x_auth_password": password,
            }
            api = weibo.API(self.app.config["CONSUMER_KEY"], self.app.config["CONSUMER_SECRET"])
            api.bind_auth()
            try:
                access_token = api.get_authorized_tokens(**params)
            except weibo.Error as e:
                flash_messages.append(u"XAuth错误：%s" % str(e))
            else:
                sid = crypto.encrypt("%s:%s" % (access_token["oauth_token"], access_token["oauth_token_secret"]),
                                     self.app.config["SECRET_KEY"])
                rss_url = urlparse.urljoin("http://" + self.request.host, self.uri_for("rss", sid=sid))
                self.render_response("rss.html", rss_url=rss_url)
                return
        else:
            flash_messages.append(u"缺少邮箱或密码！")
        self.render_response("login.html", flash_messages=flash_messages)
