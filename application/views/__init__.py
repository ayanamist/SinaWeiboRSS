from __future__ import absolute_import

from os import path
import urllib

import webapp2
from webapp2_extras import jinja2

from application import utils


class BaseHandler(webapp2.RequestHandler):
    @webapp2.cached_property
    def jinja2(self):
        default_config = jinja2.default_config
        environment_args = default_config["environment_args"]
        environment_args["auto_reload"] = False
        default_config["globals"] = {
            "app": self.app,
            "uri_for": webapp2.uri_for,
        }
        default_config["filters"] = {
            "mid2url": utils.mid2url,
            "rfc822": utils.rfc822,
            "strftime": utils.strftime,
            "quote": urllib.quote,
            "utf8": lambda x: x.encode("utf8"),
        }
        default_config["template_path"] = path.normpath(path.join(path.dirname(__file__), "../templates"))
        return jinja2.get_jinja2(app=self.app)

    def render_response(self, _template, **context):
        if "flash_messages" not in context:
            context["flash_messages"] = []
        rv = self.jinja2.render_template(_template, **context)
        self.response.write(rv)
        self.flash_messages = []
