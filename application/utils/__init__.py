# -*- coding: utf-8 -*-
from __future__ import absolute_import

import email.utils
import re
import time

from application.utils import crypto, emotions

base62 = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
base62_len = 62
url_regex = re.compile(ur"http[s]?://[a-zA-Z0-9$-_@.&#+!*(),%?]+")
name_regex = re.compile(ur"@([A-Za-z0-9\-_\u4e00-\u9fff]{2,30})")
emotion_regex = re.compile(ur"\[[^\]]+\]")


def mid2url(mid):
    mid_str = str(mid)
    output = ""
    for stop in xrange(len(mid_str), 0, -7):
        part = int(mid_str[stop - 7 if stop > 7 else 0:stop], 10)
        output_part = ""
        while part > 0:
            output_part = base62[part % base62_len] + output_part
            part //= base62_len
        output = "0" * (4 - len(output_part)) + output_part + output
    return output.lstrip("0")


def rfc822(obj):
    return email.utils.formatdate(email.utils.mktime_tz(email.utils.parsedate_tz(obj)))


def strftime(created_at):
    unix_timestamp = time.mktime(email.utils.parsedate(created_at))
    t = time.gmtime(unix_timestamp)
    now_t = time.gmtime()
    date_fmt = "%m-%d %H:%M:%S"
    if now_t.tm_year != t.tm_year:
        date_fmt = "%Y-" + date_fmt
    return time.strftime(date_fmt, t)


def expand_text(obj):
    obj = unicode(obj)
    obj = obj.replace(u"\u200B", "").replace(u"\ufeff", "")
    obj = obj.rstrip()
    obj = obj.replace('>', '&gt;').replace('<', '&lt;')
    obj = url_regex.sub(r' <a href="\g<0>">\g<0></a> ', obj)
    obj = name_regex.sub(r' <a href="http://weibo.com/n/\g<1>">@\g<1></a> ', obj)
    for s in emotion_regex.findall(obj):
        u = emotions.m.get(s)
        if u is not None:
            s2 = s.replace("[", "&#91;").replace("]", "&#93;")
            obj = obj.replace(s, r' <img render="ext" src="%s" title="%s" alt="%s" type="face"> ' % (u, s2, s2))
    obj = obj.replace("\r\n", "\n").replace("\r", "\n").replace("\n", " <br> ")
    return obj


_regex = re.compile(r"(http(?:s)?://(\w+)\.sinaimg\.cn/([a-z]+)/[a-z0-9]+\.[a-z]+)", re.I)


def original_pic(url):
    matched = _regex.match(url)
    if matched:
        return url[:matched.start(3)] + "large" + url[matched.end(3):]
    else:
        return url
