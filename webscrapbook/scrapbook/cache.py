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


StaticIndexItem = namedtuple('StaticIndexItem',
    ['event', 'level', 'id', 'type', 'marked', 'title', 'url', 'icon', 'source', 'comment'])
StaticIndexItem.__new__.__defaults__ = (None, None, None, None, None, None, None, None)

class StaticSiteGenerator():
    """Main class for static site pages generation.
    """
    RESOURCES = {
        'icon/toggle.png': 'toggle.png',
        'icon/search.png': 'search.png',
        'icon/collapse.png': 'collapse.png',
        'icon/expand.png': 'expand.png',
        'icon/external.png': 'external.png',
        'icon/comment.png': 'comment.png',
        'icon/item.png': 'item.png',
        'icon/fclose.png': 'fclose.png',
        'icon/fopen.png': 'fopen.png',
        'icon/file.png': 'file.png',
        'icon/note.png': 'note.png',
        'icon/postit.png': 'postit.png',
        }
    ITEM_TYPE_ICON = {
        '': 'icon/item.png',
        'folder': 'icon/fclose.png',
        'file': 'icon/file.png',
        'image': 'icon/file.png',
        'note': 'icon/note.png',  # ScrapBook X notex
        'postit': 'icon/postit.png',  # ScrapBook X note
        }

    def __init__(self, book, *, locale=None,
            static_index=False, rss=False,
            ):
        self.host = book.host
        self.book = book
        self.static_index = static_index
        self.locale = locale

        self.rss = rss

        self.template_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(self.host.templates),
            autoescape=jinja2.select_autoescape(['html']),
            )
        self.template_env.globals.update({
            'format_string': util.format_string,
            'i18n': self.host.get_i18n(locale),
            'bookname': book.name,
            })

        book.load_meta_files()
        book.load_toc_files()

    @dump_args
    def run(self):
        yield Info('info', 'Generating static site pages...')

        # copy resource files
        for dst, src in self.RESOURCES.items():
            yield from self._generate_resource_file(src, dst)

        # generate static site pages
        index_kwargs = dict(
            rss=self.rss,
            data_dir = util.get_relative_url(self.book.data_dir, self.book.tree_dir),
            default_icons = self.ITEM_TYPE_ICON,
            meta_cnt=max(sum(1 for _ in self.book.iter_meta_files()), 1),
            toc_cnt=max(sum(1 for _ in self.book.iter_toc_files()), 1),
            )

        if self.static_index:
            yield from self._generate_page('index.html', 'static_index.html', filename='index',
                static_index=self._generate_static_index(), **index_kwargs,
                )

        yield from self._generate_page('map.html', 'static_map.html', filename='map',
            static_index=None, **index_kwargs,
            )

        yield from self._generate_page('frame.html', 'static_frame.html')

        yield from self._generate_page('search.html', 'static_search.html',
            path=util.get_relative_url(self.book.top_dir, self.book.tree_dir),
            data_dir=util.get_relative_url(self.book.data_dir, self.book.top_dir),
            tree_dir=util.get_relative_url(self.book.tree_dir, self.book.top_dir),
            index=self.host.config['book'][self.book.id]['index'],
            )

    def _generate_resource_file(self, src, dst):
        yield Info('debug', f'Checking resource file "{dst}"')
        fsrc = self.host.get_static_file(src)
        fdst = os.path.normpath(os.path.join(self.book.tree_dir, dst))

        # check whether writing is required
        if os.path.isfile(fdst):
            if os.stat(fsrc).st_size == os.stat(fdst).st_size:
                if util.checksum(fsrc) == util.checksum(fdst):
                    yield Info('debug', f'Skipped resource file "{dst}" (up-to-date)')
                    return

        # save file
        yield Info('info', f'Generating resource file "{dst}"')
        try:
            os.makedirs(os.path.dirname(fdst), exist_ok=True)
            fsrc = self.host.get_static_file(src)
            self.book.backup(fdst)
            shutil.copyfile(fsrc, fdst)
        except OSError as exc:
            yield Info('error', f'Failed to create resource file "{dst}": {exc.strerror}', exc=exc)

    def _generate_page(self, dst, tpl, **kwargs):
        yield Info('debug', f'Checking page "{dst}"')
        fsrc = io.BytesIO()
        fdst = os.path.normpath(os.path.join(self.book.tree_dir, dst))

        template = self.template_env.get_template(tpl)
        content = template.render(**kwargs)
        fsrc.write(content.encode('UTF-8'))

        # check whether writing is required
        if os.path.isfile(fdst):
            if fsrc.getbuffer().nbytes == os.stat(fdst).st_size:
                fsrc.seek(0)
                if util.checksum(fsrc) == util.checksum(fdst):
                    yield Info('debug', f'Skipped page "{dst}" (up-to-date)')
                    return

        # save file
        yield Info('info', f'Generating page "{dst}"')
        try:
            fsrc.seek(0)
            os.makedirs(os.path.dirname(fdst), exist_ok=True)
            self.book.backup(fdst)
            with open(fdst, 'wb') as fh:
                shutil.copyfileobj(fsrc, fh)
        except OSError as exc:
            yield Info('error', f'Failed to create page file "{dst}": {exc.strerror}', exc=exc)

    def _generate_static_index(self):
        def get_class_text(classes, prefix=' '):
            if not classes:
                return ''

            c = html.escape(' '.join(classes))
            return f'{prefix}class="{c}"'

        def add_child_items(parent_id):
            nonlocal level

            try:
                toc = book.toc[parent_id]
            except KeyError:
                return

            toc = [id for id in toc if id in book.meta]
            if not toc:
                return

            yield StaticIndexItem('start-container', level)
            level += 1

            for id in toc:
                meta = book.meta[id]
                meta_type = meta.get('type', '')
                meta_index = meta.get('index', '')
                meta_title = meta.get('title', '')
                meta_source = meta.get('source', '')
                meta_icon = meta.get('icon', '')
                meta_comment = meta.get('comment', '')
                meta_marked = meta.get('marked', '')

                if meta_type != 'separator':
                    title = meta_title or id

                    if meta_type != 'folder':
                        if meta_type == 'bookmark' and meta_source:
                            href = meta_source
                        elif meta_index:
                            href = util.get_relative_url(os.path.join(book.data_dir, meta_index), book.tree_dir, path_is_dir=False)
                            hash = urlsplit(meta_source).fragment
                            if hash:
                                href += '#' + hash
                        else:
                            href = ''
                    else:
                        href = ''

                    # meta_icon is a URL
                    if meta_icon and not urlsplit(meta_icon).scheme:
                        # relative URL: tree_dir..index..icon
                        ref = util.get_relative_url(os.path.join(book.data_dir, os.path.dirname(meta_index)), book.tree_dir)
                        icon = ref + meta_icon
                    else:
                        icon = meta_icon

                else:
                    title = meta_title
                    href = ''
                    icon = ''

                yield StaticIndexItem('start', level, id, meta_type, meta_marked, title, href, icon, meta_source, meta_comment)

                # do not output children of a circular item
                if id not in id_chain:
                    level += 1
                    id_chain.add(id)
                    yield from add_child_items(id)
                    id_chain.remove(id)
                    level -= 1

                yield StaticIndexItem('end', level, id, meta_type, meta_marked, title, href, icon, meta_source, meta_comment)

            level -= 1
            yield StaticIndexItem('end-container', level)

        book = self.book
        level = 0
        id_chain = {'root'}
        yield from add_child_items('root')

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
                lh = nullcontext() if no_lock else book.get_tree_lock().acquire()
                with lh:
                    if static_site:
                        generator = StaticSiteGenerator(
                            book,
                            static_index=static_index,
                            locale=locale, rss=bool(rss_root),
                            )
                        yield from generator.run()

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
