from __future__ import absolute_import

import os

import webapp2

try:
    from google.appengine.api import urlfetch

    urlfetch.set_default_fetch_deadline(30)
except ImportError:
    pass

config = dict((name, os.environ.get(name)) for name in (
    "CONSUMER_KEY",
    "CONSUMER_SECRET",
    "CONSUMER_DOMAIN",
    "SECRET_KEY",
))

app = webapp2.WSGIApplication([
    webapp2.Route("/", handler="application.views.login.Login", name="login"),
    webapp2.Route("/rss/<sid>", handler="application.views.rss.RSS", name="rss"),
], config=config, debug=True)
