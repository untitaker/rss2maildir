# coding=utf-8

# rss2maildir.py - RSS feeds to Maildir 1 email per item
#
# Copyright (C) 2007  Brett Parker <iDunno@sommitrealweird.co.uk>
# Copyright (C) 2011  Justus Winter <4winter@informatik.uni-hamburg.de>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sys
import os
import errno
import random
import socket
import string
import urllib
import httplib
import logging

if sys.version_info >= (2, 6):
    import hashlib as md5
else:
    import md5


def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as e:
        if e.errno != errno.EEXIST or not os.path.isdir(path):
            raise


def make_maildir(path):
    for dirname in (os.path.join(path, subdir)
                    for subdir in ('cur', 'tmp', 'new')):
        mkdir_p(dirname)


def open_url(method, url, max_redirects=3,
             redirect_on_status=(301, 302, 303, 307)):
    log = logging.getLogger('%s %s' % (method, url))

    redirectcount = 0
    while redirectcount < max_redirects:
        (type_, rest) = urllib.splittype(url)
        (host, path) = urllib.splithost(rest)
        (host, port) = urllib.splitport(host)

        if type_ == "https":
            if port is None:
                port = 443
        elif port is None:
            port = 80

        try:
            if type_ == "http":
                conn = httplib.HTTPConnection("%s:%s" % (host, port))
            else:
                conn = httplib.HTTPSConnection("%s:%s" % (host, port))
            conn.request(method, path)
        except (httplib.HTTPException, socket.error) as e:
            log.warning('http request failed: %s' % str(e))
            return None

        response = conn.getresponse()
        if response.status == 200:
            return response
        elif response.status in redirect_on_status:
            headers = response.getheaders()
            for header in headers:
                if header[0] == "location":
                    url = header[1]
        else:
            log.warning('Received unexpected status: %i %s' % (
                response.status, response.reason))
            return None

        redirectcount = redirectcount + 1

    log.warning('Maximum number of redirections reached')
    return None


def generate_random_string(
        length, character_set=string.ascii_letters + string.digits):
    return ''.join(random.choice(character_set) for n in range(length))


def compute_hash(data):
    return md5.md5(data).hexdigest()

def maildirname_join(*names):
    stripped = '.'.join(name.strip('.') for name in names)
    prefix = '.' if names[0].startswith('.') else ''
    suffix = '.' if names[-1].endswith('.') else ''
    return prefix + stripped + suffix
