"""Generator of fulltext cache and/or static site pages.
"""
import os
import traceback
import shutil
import io
import zipfile
import mimetypes
import time
import re
import html
import copy
import itertools
import functools
from collections import namedtuple, UserDict
from urllib.parse import urlsplit, urljoin, quote, unquote
from datetime import datetime, timezone

import jinja2
from lxml import etree

from webscrapbook.utils.dump_args import dump_args

from .host import Host
from .. import util
from ..util import Info
from .._compat import zip_stream
from .._compat.contextlib import nullcontext


class MutatingDict(UserDict):
    """Support adding during dict iteration.
    """
    def __init__(self, *args, **kwargs):
        self._keys = []

        # this calls __setitem__ internally
        super().__init__(*args, **kwargs)

    def __setitem__(self, key, value):
        if key not in self:
            self._keys.append(key)
        super().__setitem__(key, value)

    def __iter__(self):
        return iter(self._keys)

    def __delitem__(self, key):
        return NotImplemented

@dump_args
def generate(root, book_ids=None, item_ids=None, *,
        config=None, no_lock=False, no_backup=False,
        fulltext=True, inclusive_frames=True, recreate=False,
        static_site=False, static_index=False, locale=None,
        rss_root=None, rss_item_count=50):
    """
    deprecated:
        rss_root: no use
        fulltext: no use
        static_site: no use
    """
    start = time.time()

    host = Host(root, config)

    if not no_backup:
        host.init_backup(note='cache')
        yield Info('info', f'Prepared backup at "{host.get_subpath(host._backup_dir)}".')

    try:
        # cache all books if none specified
        for book_id in book_ids or host.books:
            try:
                book = host.books[book_id]
            except KeyError:
                # skip invalid book ID
                yield Info('warn', f'Skipped invalid book "{book_id}".')
                continue

            yield Info('debug', f'Loading book "{book_id}".')
            try:
                if book.no_tree:
                    yield Info('info', f'Skipped book "{book_id}" ("{book.name}") (no_tree).')
                    continue

                yield Info('info', f'Caching book "{book_id}" ({book.name}).')

            except Exception as exc:
                traceback.print_exc()
                yield Info('critical', str(exc), exc=exc)
            else:
                yield Info('info', 'Done.')

            yield Info('info', '----------------------------------------------------------------------')
    finally:
        if not no_backup:
            host.init_backup(False)

    elapsed = time.time() - start
    yield Info('info', f'Time spent: {elapsed} seconds.')
