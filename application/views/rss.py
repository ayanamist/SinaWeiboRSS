# coding=utf-8
from __future__ import absolute_import

import json
import logging
import re
import urllib
import zlib
from collections import defaultdict

from google.appengine.api import memcache
from google.appengine.api import urlfetch

from application import views
from application.utils import crypto

tcn_regex = re.compile(r"http[s]?://t\.cn/[a-zA-Z0-9$-_@.&#+!*(),%?]+")


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
            content = urlfetch.fetch("https://api.weibo.com/2/statuses/home_timeline.json?" + urllib.urlencode({
                "count": 100,
                "base_app": 0,
                "feature": 0,
                "trim_user": 0,
            }), headers={"Authorization": "OAuth2 " + access_token}).content
            body = json.loads(content)
            if "error" in body:
                logging.error("error: %s", content)
                self.response.status_int = 500
                self.response.write(body["error"])
                return
            results = body["statuses"]
            # 读取超过140字的全文
            long_text_ids = []
            long_text_map = {}
            for status in results:
                if status["isLongText"]:
                    long_text_ids.append(status["idstr"])
                status = status.get("retweeted_status")
                if status is not None:
                    if status["isLongText"]:
                        long_text_ids.append(status["idstr"])
            logging.debug("long_text_ids size=%d: %s", len(long_text_ids), long_text_ids)
            if len(long_text_ids) > 0:
                rpcs = []
                max_size = 50
                for chunk in (long_text_ids[x:x + max_size] for x in xrange(0, len(long_text_ids), max_size)):
                    ids = ",".join(chunk)
                    rpc = urlfetch.create_rpc()
                    urlfetch.make_fetch_call(rpc,
                                             "https://api.weibo.com/2/statuses/show_batch.json?" + urllib.urlencode({
                                                 "ids": ids,
                                                 "isGetLongText": "1",
                                             }), headers={"Authorization": "OAuth2 " + access_token})
                    rpc.ids = ids
                    rpcs.append(rpc)
                for rpc in rpcs:
                    try:
                        body = json.loads(rpc.get_result().content)
                    except Exception as e:
                        body = {"error": str(e)}
                    if "error" in body:
                        logging.warn("show_batch %s error: %s", rpc.ids, str(body["error"]))
                    elif "statuses" in body:
                        for status in body["statuses"]:
                            if "longText" in status:
                                long_text_map[status["idstr"]] = status["longText"]["longTextContent"]
            logging.debug("long_text_map size=%d", len(long_text_map))
            if len(long_text_map) > 0:
                def expand_long_text(status):
                    if status["isLongText"]:
                        text = long_text_map.get(status["idstr"])
                        if text is not None:
                            logging.debug("replace long text for %s: %s", status["idstr"], text)
                            status["text"] = text
                            status["isLongText"] = False

                for status in results:
                    expand_long_text(status)
                    status = status.get("retweeted_status")
                    if status is not None:
                        expand_long_text(status)
            # 将t.cn短链接展开
            tcn_id2url = defaultdict(set)
            all_tcn_urls = set()

            def extract_tcn_urls(status):
                tcn_urls = tcn_regex.findall(status["text"])
                idstr = status["idstr"]
                tcn_id2url[idstr].update(tcn_urls)
                all_tcn_urls.update(tcn_urls)

            for status in results:
                extract_tcn_urls(status)
                status = status.get("retweeted_status")
                if status is not None:
                    extract_tcn_urls(status)
            logging.debug("all_tcn_urls size=%d", len(all_tcn_urls))
            all_tcn_urls = list(all_tcn_urls)
            tcn_short2long = {}
            memcache_client = memcache.Client()
            cached_result = memcache_client.get_multi(all_tcn_urls, "tcn#")
            tcn_short2long.update(cached_result)
            all_tcn_urls = filter(lambda x: x not in tcn_short2long, all_tcn_urls)
            rpcs = []
            max_size = 20
            for chunk in (all_tcn_urls[x:x + max_size] for x in xrange(0, len(all_tcn_urls), max_size)):
                rpc = urlfetch.create_rpc()
                rpc.chunk = chunk
                urlfetch.make_fetch_call(rpc, "https://api.weibo.com/2/short_url/expand.json?"
                                         + urllib.urlencode([("url_short", x) for x in chunk]),
                                         headers={"Authorization": "OAuth2 " + access_token})
                rpcs.append(rpc)
            for rpc in rpcs:
                try:
                    result = json.loads(rpc.get_result().content)
                except Exception as e:
                    result = {"error": str(e)}
                if "error" in result:
                    logging.warn("expand %s error: %s", str(rpc.chunk), result["error"])
                elif "urls" in result:
                    for u in result["urls"]:
                        if u["result"] and u["url_long"] != "":
                            tcn_short2long[u["url_short"]] = u["url_long"]
            logging.debug("tcn_short2long size=%d", len(tcn_short2long))
            if len(tcn_short2long) > 0:
                memcache_client.set_multi(tcn_short2long, 86400, "tcn#")

                def expand_url(status):
                    idstr = status["idstr"]
                    tcn_urls = tcn_id2url[idstr]
                    if len(tcn_urls) > 0:
                        text = status["text"]
                        for short_url in tcn_urls:
                            long_url = tcn_short2long.get(short_url)
                            if long_url is not None:
                                text = text.replace(short_url, long_url)
                        status["text"] = text

                for status in results:
                    expand_url(status)
                    status = status.get("retweeted_status")
                    if status is not None:
                        expand_url(status)

            # 在jinja模板里做escape会把后面的filter也escape了，所以只好在这里自己做一下
            def escape(status):
                status["text"] = status["text"].replace('&', '&amp;').replace('>', '&gt;').replace('<', '&lt;')

            for status in results:
                escape(status)
                status = status.get("retweeted_status")
                if status is not None:
                    escape(status)
            # 将结果缓存
            memcache.set(sid, zlib.compress(json.dumps(results), 9), time=120)
        else:
            logging.debug("sid %s from cache", sid)
        self.response.headers["Content-Type"] = "application/rss+xml; charset=utf-8"
        self.render_response("rss.xml", results=results)
