from __future__ import absolute_import

import os
import sys

import webapp2

lib_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "lib"))
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
    ("/", ""),
], config=config, debug=True)

