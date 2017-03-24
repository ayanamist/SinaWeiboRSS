from __future__ import absolute_import

import os
import sys

import webapp2
try:
    from google.appengine.api import urlfetch
    urlfetch.set_default_fetch_deadline(10)
except ImportError:
    pass

lib_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "vendor"))
for dir_path in os.listdir(lib_path):
    sys.path.insert(0, os.path.join(lib_path, dir_path))

from application.utils import monkey_patch

monkey_patch.patch_all()

config = dict((name, os.environ[name]) for name in (
    "CONSUMER_KEY",
    "CONSUMER_SECRET",
    "SECRET_KEY",
))

app = webapp2.WSGIApplication([
    webapp2.Route("/", handler="application.views.login.Login", name="login"),
    webapp2.Route("/rss/<sid>", handler="application.views.rss.RSS", name="rss"),
    webapp2.Route("/proxy/<url>/<md5hash>", handler="application.views.proxy.Proxy", name="proxy"),
], config=config, debug=True)

