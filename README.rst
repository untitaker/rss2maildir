===========
rss2maildir
===========

Introduction
============

rss2maildir takes rss feeds and creates a maildir of messages for each of the
feeds, new items become "new", updated entries get redelivered as new messages.
Each feed becomes it's own maildir which can be named as you like.

Installation
============

Clone this repository or download the ZIP archive. Then run::

  ./setup.py install

to install the Python package and the command-line tool.

Usage
=====

Configuration
-------------

Create a config file containing the feeds and their "names" - the names will be
used as the directory name of the maildir for the feed. A complete example with
default values can be found at `rss2maildir/rss2maildir.defaults.example`::

  [general]
  state_dir = "~/rss2maildir/state.d"  # default: cwd + "state"
  maildir_root = "~/mail/feeds"  # default: cwd + "RSSMaildir"

  [http://example.com/feed/]
  name = "The Example Feed"
  email = bruce.wayne@example.com  # the author of the blog
  maildir = "example"  # items now get stored in ~/mail/feeds/example/


It doesn't really matter where you save the config file.

Execution
---------

During installation, `setup.py` should have installed the command-line utility
`rss2maildir` into your path. Executing::

  rss2maildir -c ./path/to/your.config

will look for new feed items and place them into the maildirs. In order to
recieve new items into your maildirs, you need to execute it regularly.
