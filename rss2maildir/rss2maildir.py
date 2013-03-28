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


def update_feeds(settings=None):
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

def main():
    import sys
    import os
    import logging
    from optparse import OptionParser

    settings = get_default_settings()

    oparser = OptionParser()
    oparser.add_option(
        '-c', '--conf', dest = 'conf',
        help = 'location of config file'
    )
    oparser.add_option(
        '-s', '--statedir', dest = 'statedir',
        help = 'location of directory to store state in'
    )
    oparser.add_option(
        '-v', '--verbose', dest = 'verbosity', action = 'count', default = 0,
        help = 'be more verbose, can be given multiple times'
    )

    options, args = oparser.parse_args()

    loglevel = {
        0: logging.WARNING,
        1: logging.INFO,
        2: logging.DEBUG,
    }[min(2, options.verbosity)]
    logging.basicConfig(level = loglevel)

    # check for the configfile

    configfile = None
    configfile_locations = [
        os.path.join(os.environ.get('XDG_CONFIG_HOME',
                                    os.path.expanduser('~/.config')),
                     'rss2maildir', 'config'),
        os.path.expanduser('~/.rss2maildir.conf'),
        '/etc/rss2maildir.conf',
    ]

    if options.conf != None:
        if not os.path.exists(options.conf):
            sys.exit('Config file %s does not exist. Exiting.' % options.conf)
        configfile_locations.insert(0, options.conf)

    found_config = False
    for configfile in configfile_locations:
        if settings.read(configfile):
            found_config = True
            break

    if not found_config:
        sys.exit('No config file found')

    if options.statedir != None:
        settings['state_dir'] = options.statedir
    elif not 'state_dir' in settings:
        settings['state_dir'] = os.path.join(
            os.environ.get('XDG_DATA_HOME', '~/.local/share'),
            'rss2maildir'
        )

    update_feeds(settings)
