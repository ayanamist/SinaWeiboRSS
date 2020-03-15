# -*- coding: utf-8 -*-
from __future__ import absolute_import

from application import views
from application.utils import mid2url


class JumpHandler(views.BaseHandler):
    def get(self, app_url, international_app_url, web_url):
        if "Mobile" not in self.request.user_agent:
            self.redirect(web_url)
        else:
            self.render_response("jump.html", app_url=app_url, web_url=web_url, international_app_url=international_app_url)


class Detail(JumpHandler):
    def get(self, uid, mid):
        app_url = "sinaweibo://detail?mblogid=" + mid
        international_app_url = "weibointernational://detail?weiboid=" + mid
        web_url = "https://weibo.com/%s/%s" % (uid, mid2url(mid))
        super(Detail, self).get(app_url, international_app_url, web_url)


class UserProfile(JumpHandler):
    def get(self, uid, nick):
        app_url = "sinaweibo://userinfo?userid=" + uid
        international_app_url = "weibointernational://userprofile?userid=" + uid
        web_url = "https://weibo.com/n/" + nick
        super(UserProfile, self).get(app_url, international_app_url, web_url)
