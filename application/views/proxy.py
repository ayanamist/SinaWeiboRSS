from __future__ import absolute_import

import urllib

import requests

from application import utils
from application import views


class Proxy(views.BaseHandler):
    def get(self, url, md5hash):
        url = urllib.unquote(url)
        if utils.md5hash(url) != md5hash:
            self.response.status_int = 403
            return
        r = requests.get(url)
        self.response.headers.update(r.headers)
        self.response.write(r.content)
