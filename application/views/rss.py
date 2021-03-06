# coding=utf-8
from __future__ import absolute_import

import functools
import json
import logging
import re
import urllib
import urlparse
import zlib
from collections import defaultdict

from google.appengine.api import memcache
from google.appengine.api import urlfetch

from application import views
from application.utils import crypto

tcn_regex = re.compile(r"http[s]?://t\.cn/[a-zA-Z0-9$-_@.&#+!*(),%?]+")
utm_queries = {"utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term"}


class RSS(views.BaseHandler):
    def get(self, sid):
        memcache_client = memcache.Client()
        results = memcache_client.get(sid)
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
                "isGetLongText": "1",
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
                if status.get("isLongText", True):
                    long_text_ids.append(status["idstr"])
                status = status.get("retweeted_status")
                if status is not None:
                    if status.get("isLongText", True):
                        long_text_ids.append(status["idstr"])
            logging.debug("long_text_ids before cache size=%d", len(long_text_ids))
            if len(long_text_ids):
                cached_result = memcache_client.get_multi(long_text_ids, "long#")
                long_text_map.update(cached_result)
                long_text_ids = filter(lambda x: x not in long_text_map, long_text_ids)
            logging.debug("long_text_ids after cache size=%d", len(long_text_ids))
            long_text_ids = sorted(list(set(long_text_ids)))
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
                memcache_client.set_multi(long_text_map, time=86400, key_prefix="long#")

                def expand_long_text(status):
                    if status.get("isLongText", True):
                        text = long_text_map.get(status["idstr"])
                        if text is not None:
                            logging.debug("replace long text for %s", status["idstr"])
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
            logging.debug("all_tcn_urls before cache size=%d", len(all_tcn_urls))
            all_tcn_urls = list(all_tcn_urls)
            tcn_short2long = {}
            cached_result = memcache_client.get_multi(all_tcn_urls, "tcn#")
            tcn_short2long.update(cached_result)
            all_tcn_urls = filter(lambda x: x not in tcn_short2long, all_tcn_urls)
            logging.debug("all_tcn_urls after cache size=%d", len(all_tcn_urls))
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
                        url_long = u["url_long"]
                        if u["result"] and url_long != "":
                            o = urlparse.urlparse(url_long, scheme="http", allow_fragments=True)
                            qsl = filter(lambda x: x[0] not in utm_queries, urlparse.parse_qsl(o.query, True))
                            o = urlparse.ParseResult(o.scheme, o.netloc, o.path, o.params,
                                                     urllib.urlencode(encode_obj(qsl)),
                                                     o.fragment)
                            url_long = urlparse.urlunparse(o)
                            if url_long:
                                tcn_short2long[u["url_short"]] = url_long
            logging.debug("tcn_short2long size=%d", len(tcn_short2long))
            if len(tcn_short2long) > 0:
                memcache_client.set_multi(tcn_short2long, time=86400, key_prefix="tcn#")

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

            # 将结果缓存
            memcache_client.set(sid, zlib.compress(json.dumps(results), 9), time=120)
        else:
            logging.debug("sid %s from cache", sid)
        self.response.headers["Content-Type"] = "application/rss+xml; charset=utf-8"
        self.render_response("rss.xml", results=results,
                             abs_uri_for=functools.partial(self.uri_for, _full=True, _scheme="https"))


def encode_obj(in_obj):
    def encode_list(in_list):
        out_list = []
        for el in in_list:
            out_list.append(encode_obj(el))
        return out_list

    def encode_dict(in_dict):
        out_dict = {}
        for k, v in in_dict.iteritems():
            out_dict[k] = encode_obj(v)
        return out_dict

    if isinstance(in_obj, unicode):
        return in_obj.encode('utf-8')
    elif isinstance(in_obj, list):
        return encode_list(in_obj)
    elif isinstance(in_obj, tuple):
        return tuple(encode_list(in_obj))
    elif isinstance(in_obj, dict):
        return encode_dict(in_obj)

    return in_obj
