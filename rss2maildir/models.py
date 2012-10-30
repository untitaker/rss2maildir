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

import logging
import feedparser

from .utils import open_url, generate_random_string, mkdir_p

log = logging.getLogger('rss2maildir:models')

import os
import email
import socket
from datetime import datetime

from html2text import html2text
from .utils import compute_hash
from .settings import settings

import dbm
import marshal
serialize = marshal.dumps
deserialize = marshal.loads


class Feed(object):
    def __init__(self, database, url):
        self.database = database
        self.url = url
        self.name = url

    def is_changed(self):
        try:
            previous_data = self.database.get_feed_metadata(self.url)
        except KeyError:
            return True

        response = open_url('HEAD', self.url)
        if not response:
            log.warning('Fetching feed %s failed' % self.name)
            return True

        result = False
        for key, value in response.getheaders():
            if previous_data.get(key, None) != value:
                result = True
                break

        return result

    relevant_headers = ('content-md5', 'etag', 'last-modified',
                        'content-length')

    def new_items(self):
        if not self.is_changed():
            log.info('Feed %s not changed, skipping' % self.url)
            return

        response = open_url('GET', self.url)
        if not response:
            log.warning('Fetching feed %s failed' % (self.url))
            return

        parsed_feed = feedparser.parse(response)
        for item in (Item(self, feed_item) for feed_item in
                     parsed_feed['items']):
            if self.database.seen_before(item):
                log.info('Item %s already seen, skipping' % item.link)
                continue

            yield item
            self.database.mark_seen(item)

        data = dict((key, value) for key, value in response.getheaders()
                    if key in self.relevant_headers)
        if data:
            self.database.set_feed_metadata(self.url, data)


class Item(object):
    def __init__(self, feed, feed_item):
        self.feed = feed

        self.author = feed_item.get('author', self.feed.url)
        self.title = feed_item['title']
        self.link = feed_item['link']

        if 'content' in feed_item:
            self.content = feed_item['content'][0]['value']
        else:
            if 'description' in feed_item:
                self.content = feed_item['description']
            else:
                self.content = u''

        self.md5sum = compute_hash(self.content.encode('utf-8'))

        self.guid = feed_item.get('guid', None)
        if self.guid:
            self.db_guid_key = (self.feed.url + u'|' +
                                self.guid).encode('utf-8')
        else:
            self.db_guid_key = None

        self.db_link_key = (self.feed.url + u'|' +
                            feed_item['link']).encode('utf-8')

        self.createddate = datetime.now().strftime('%a, %e %b %Y %T -0000')
        updated_parsed = feed_item['updated_parsed'][0:6]
        try:
            self.createddate = datetime(*updated_parsed) \
                .strftime('%a, %e %b %Y %T -0000')
        except TypeError as e:
            log.warning('Parsing date %s failed: %s' % (updated_parsed, str(e)))

        self.previous_message_id = None
        self.message_id = '<%s.%s@%s>' % (
            datetime.now().strftime("%Y%m%d%H%M"),
            generate_random_string(6),
            socket.gethostname()
        )

    def __getitem__(self, key):
        return getattr(self, key)

    text_template = u'%(text_content)s\n\nItem URL: %(link)s'
    html_template = u'%(html_content)s\n<p>Item URL: <a href="%(link)s">%(link)s</a></p>'

    def create_message(self, include_html_part=True, item_filters=None):
        item = self
        if item_filters:
            for item_filter in item_filters:
                item = item_filter(item)
                if not item:
                    return False

        message = email.MIMEMultipart.MIMEMultipart('alternative')

        message.set_unixfrom('%s <rss2maildir@localhost>' % item.feed.url)
        message['From'] = '%s <rss2maildir@localhost>' % item.author
        message['To'] = '%s <rss2maildir@localhost>' % item.feed.url

        title = item.title.replace(u'<', u'&lt;').replace(u'>', u'&gt;')
        message['Subject'] = html2text(title).strip()

        message['Message-ID'] = item.message_id
        if item.previous_message_id:
            message['References'] = item.previous_message_id

        message['Date'] = item.createddate
        message['X-rss2maildir-rundate'] = \
                datetime.now().strftime('%a, %e %b %Y %T -0000')

        textpart = email.MIMEText.MIMEText(
            (item.text_template % item).encode('utf-8'),
            'plain', 'utf-8')
        message.set_default_type('text/plain')
        message.attach(textpart)

        if include_html_part:
            htmlpart = email.MIMEText.MIMEText(
                (item.html_template % item).encode('utf-8'),
                'html', 'utf-8')
            message.attach(htmlpart)

        return message

    @property
    def text_content(self):
        return html2text(self.content)

    @property
    def html_content(self):
        return self.content

    def deliver(self, message, maildir):
        # start by working out the filename we should be writting to, we do
        # this following the normal maildir style rules
        file_name = '%i.%s.%s.%s' % (
            os.getpid(),
            socket.gethostname(),
            generate_random_string(10),
            datetime.now().strftime('%s')
        )

        tmp_path = os.path.join(maildir, 'tmp', file_name)
        handle = open(tmp_path, 'w')
        handle.write(message.as_string())
        handle.close()

        # now move it in to the new directory
        new_path = os.path.join(maildir, 'new', file_name)
        os.link(tmp_path, new_path)
        os.unlink(tmp_path)


class Database(object):
    def __init__(self, path):
        try:
            mkdir_p(path)
        except OSError as e:
            raise RuntimeError(
                "Couldn't create statedir %s: %s" % (settings['state_dir'], str(e)))

        self.feeds = dbm.open(os.path.join(path, "feeds"), "c")
        self.seen = dbm.open(os.path.join(path, "seen"), "c")

    def __del__(self):
        self.feeds.close()
        self.seen.close()

    def seen_before(self, item):
        if item.db_guid_key:
            if item.db_guid_key in self.seen:
                data = deserialize(self.seen[item.db_guid_key])
                if data['contentmd5'] == item.md5sum:
                    return True

        if item.db_link_key in self.seen:
            data = deserialize(self.seen[item.db_link_key])

            if 'message-id' in data:
                item.previous_message_id = data['message-id']

            if data['contentmd5'] == item.md5sum:
                return True

        return False

    def mark_seen(self, item):
        if item.previous_message_id:
            item.message_id = item.previous_message_id + " " + item.message_id

        data = serialize({
            'message-id': item.message_id,
            'created': item.createddate,
            'contentmd5': item.md5sum
        })

        if item.guid and item.guid != item.link:
            self.seen[item.db_guid_key] = data
            try:
                previous_data = deserialize(self.seen[item.db_link_key])
                newdata = serialize({
                    'message-id': item.message_id,
                    'created': previous_data['created'],
                    'contentmd5': previous_data['contentmd5']
                })
                self.seen[item.db_link_key] = newdata
            except:
                self.seen[item.db_link_key] = data
        else:
            self.seen[item.db_link_key] = data

    def get_feed_metadata(self, url):
        return deserialize(self.feeds[url])

    def set_feed_metadata(self, url, data):
        self.feeds[url] = serialize(data)
