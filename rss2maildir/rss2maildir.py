# coding=utf-8

# rss2maildir.py - RSS feeds to Maildir 1 email per item
# Copyright (C) 2007  Brett Parker <iDunno@sommitrealweird.co.uk>
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

import os
import logging
import imp

from .models import Database, Feed
from .settings import FeedConfigParser
from .utils import make_maildir

log = logging.getLogger('rss2maildir')
default_config_path = os.path.join(os.path.dirname(__file__), 'rss2maildir.defaults.conf')

def get_default_settings():
    settings = FeedConfigParser()
    settings.readfp(open(default_config_path))
    return settings


def main(settings=None):
    database = Database(os.path.expanduser(settings['state_dir']))

    for url in settings.feeds():
        feed = Feed(settings, database, url)
        maildir = os.path.join(os.path.expanduser(settings['maildir_root']), feed.maildir_name)

        try:
            make_maildir(maildir)
        except OSError as e:
            log.warning('Could not create maildir %s: %s' % (maildir, str(e)))
            log.warning('Skipping feed %s' % feed.url)
            continue

        # get item filters
        if 'item_filters' in settings:
            item_filters = imp.load_source(
                'item_filters',
                settings['item_filters']).get_filters()

        # right - we've got the directories, we've got the url, we know the
        # url... lets play!

        for item in feed.new_items():
            message = item.create_message(
                include_html_part=settings.getboolean(feed.url, 'include_html_part'),
                item_filters=item_filters
            )
            if item:
                item.deliver(message, maildir)
