from unittest import mock
import unittest
import os
import shutil
import io
import zipfile
import time
import functools
import collections
from datetime import datetime, timezone

from lxml import etree

from webscrapbook import WSB_DIR
from webscrapbook.scrapbook.host import Host
from webscrapbook.scrapbook import cache as wsb_cache

root_dir = os.path.abspath(os.path.dirname(__file__))
test_root = os.path.join(root_dir, 'test_scrapbook_cache')

def setUpModule():
    # mock out user config
    global mockings
    mockings = [
        mock.patch('webscrapbook.scrapbook.host.WSB_USER_DIR', os.path.join(test_root, 'wsb')),
        mock.patch('webscrapbook.WSB_USER_DIR', os.path.join(test_root, 'wsb')),
        mock.patch('webscrapbook.WSB_USER_CONFIG', test_root),
        ]
    for mocking in mockings:
        mocking.start()

def tearDownModule():
    # stop mock
    for mocking in mockings:
        mocking.stop()

class TestCache(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.maxDiff = 8192
        cls.test_root = os.path.join(test_root, 'general')
        cls.test_config = os.path.join(cls.test_root, WSB_DIR, 'config.ini')

    def tearDown(self):
        """Remove general temp test folder
        """
        try:
            shutil.rmtree(self.test_root)
        except NotADirectoryError:
            os.remove(self.test_root)
        except FileNotFoundError:
            pass

class TestFuncGenerate(TestCache):
    @mock.patch('webscrapbook.scrapbook.cache.Host')
    def test_param_root(self, mock_host):
        for info in wsb_cache.generate(self.test_root):
            pass

        mock_host.assert_called_once_with(self.test_root, None)

    @mock.patch('webscrapbook.scrapbook.cache.Host')
    def test_param_config(self, mock_host):
        for info in wsb_cache.generate(self.test_root, config={}):
            pass

        mock_host.assert_called_once_with(self.test_root, {})

    @mock.patch('webscrapbook.scrapbook.host.Book.get_tree_lock')
    def test_param_no_lock01(self, mock_func):
        for info in wsb_cache.generate(self.test_root, no_lock=False):
            pass

        mock_func.assert_called_once_with()

    @mock.patch('webscrapbook.scrapbook.host.Book.get_tree_lock')
    def test_param_no_lock02(self, mock_func):
        for info in wsb_cache.generate(self.test_root, no_lock=True):
            pass

        mock_func.assert_not_called()

    @mock.patch('webscrapbook.scrapbook.host.Book')
    def test_param_book_ids01(self, mock_book):
        """Include effective provided IDs"""
        os.makedirs(os.path.dirname(self.test_config))
        with open(self.test_config, 'w', encoding='UTF-8') as f:
            f.write("""\
[book "id1"]

[book "id2"]

[book "id4"]

[book "id5"]
""")

        for info in wsb_cache.generate(self.test_root, book_ids=['', 'id1', 'id2', 'id3', 'id4']):
            pass

        self.assertListEqual(mock_book.call_args_list, [
            mock.call(mock.ANY, ''),
            mock.call(mock.ANY, 'id1'),
            mock.call(mock.ANY, 'id2'),
            mock.call(mock.ANY, 'id4'),
            ])

    @mock.patch('webscrapbook.scrapbook.host.Book')
    def test_param_book_ids02(self, mock_book):
        """Include all available IDs if None provided"""
        os.makedirs(os.path.dirname(self.test_config))
        with open(self.test_config, 'w', encoding='UTF-8') as f:
            f.write("""\
[book "id1"]

[book "id2"]

[book "id4"]

[book "id5"]
""")

        for info in wsb_cache.generate(self.test_root):
            pass

        self.assertListEqual(mock_book.call_args_list, [
            mock.call(mock.ANY, ''),
            mock.call(mock.ANY, 'id1'),
            mock.call(mock.ANY, 'id2'),
            mock.call(mock.ANY, 'id4'),
            mock.call(mock.ANY, 'id5'),
            ])

    @mock.patch('webscrapbook.scrapbook.host.Book.get_tree_lock')
    def test_no_tree(self, mock_lock):
        """Books with no_tree=True should be skipped."""
        os.makedirs(os.path.dirname(self.test_config))
        with open(self.test_config, 'w', encoding='UTF-8') as f:
            f.write("""\
[book ""]
no_tree = true
""")

        for info in wsb_cache.generate(self.test_root):
            pass

        mock_lock.assert_not_called()

    @mock.patch('webscrapbook.scrapbook.cache.StaticSiteGenerator')
    def test_param_static_site01(self, mock_cls):
        for info in wsb_cache.generate(self.test_root, static_site=True):
            pass

        mock_cls.assert_called_once()

    @mock.patch('webscrapbook.scrapbook.cache.StaticSiteGenerator')
    def test_param_static_site02(self, mock_cls):
        for info in wsb_cache.generate(self.test_root, static_site=False):
            pass

        mock_cls.assert_not_called()

    @mock.patch('webscrapbook.scrapbook.cache.StaticSiteGenerator')
    def test_param_static_index01(self, mock_cls):
        for info in wsb_cache.generate(self.test_root, static_site=True, static_index=True):
            pass

        self.assertTrue(mock_cls.call_args[1]['static_index'])

    @mock.patch('webscrapbook.scrapbook.cache.StaticSiteGenerator')
    def test_param_static_index02(self, mock_cls):
        for info in wsb_cache.generate(self.test_root, static_site=True, static_index=False):
            pass

        self.assertFalse(mock_cls.call_args[1]['static_index'])

    @mock.patch('webscrapbook.scrapbook.cache.StaticSiteGenerator')
    def test_param_locale(self, mock_cls):
        for info in wsb_cache.generate(self.test_root, static_site=True, locale='zh_TW'):
            pass

        self.assertEqual(mock_cls.call_args[1]['locale'], 'zh_TW')

    @mock.patch('webscrapbook.scrapbook.cache.StaticSiteGenerator')
    def test_param_rss_root01(self, mock_ssg, mock_rss):
        for info in wsb_cache.generate(self.test_root, static_site=True, rss_root='http://example.com:8000/wsb/'):
            pass

        self.assertTrue(mock_ssg.call_args[1]['rss'])
        mock_rss.assert_called_once()

    @mock.patch('webscrapbook.scrapbook.cache.StaticSiteGenerator')
    def test_param_rss_root02(self, mock_ssg, mock_rss):
        for info in wsb_cache.generate(self.test_root, static_site=True, rss_root=None):
            pass

        self.assertFalse(mock_ssg.call_args[1]['rss'])
        mock_rss.assert_not_called()

    @mock.patch('webscrapbook.scrapbook.host.Host.get_subpath', lambda *_: '')
    @mock.patch('webscrapbook.scrapbook.host.Host.init_backup')
    def test_no_backup01(self, mock_func):
        for info in wsb_cache.generate(self.test_root, static_site=True, no_backup=False):
            pass

        self.assertEqual(mock_func.call_args_list, [mock.call(note='cache'), mock.call(False)])

    @mock.patch('webscrapbook.scrapbook.host.Host.init_backup')
    def test_no_backup02(self, mock_func):
        for info in wsb_cache.generate(self.test_root, static_site=True, no_backup=True):
            pass

        mock_func.assert_not_called()

class TestStaticSiteGenerator(TestCache):
    @classmethod
    def setUpClass(cls):
        cls.maxDiff = 8192
        cls.test_root = os.path.join(test_root, 'general')
        cls.test_config = os.path.join(cls.test_root, WSB_DIR, 'config.ini')
        cls.test_tree = os.path.join(cls.test_root, WSB_DIR, 'tree')

    def setUp(self):
        """Generate general temp test folder
        """
        try:
            shutil.rmtree(self.test_root)
        except NotADirectoryError:
            os.remove(self.test_root)
        except FileNotFoundError:
            pass

        os.makedirs(self.test_tree)

    def test_update01(self):
        """Create nonexisting files"""
        check_files = [
            'icon/toggle.png',
            'icon/search.png',
            'icon/collapse.png',
            'icon/expand.png',
            'icon/external.png',
            'icon/item.png',
            'icon/fclose.png',
            'icon/fopen.png',
            'icon/file.png',
            'icon/note.png',
            'icon/postit.png',
            'index.html',
            'map.html',
            'frame.html',
            'search.html',
            ]

        book = Host(self.test_root).books['']
        generator = wsb_cache.StaticSiteGenerator(book, static_index=True)
        for info in generator.run():
            pass

        orig_stats = {}
        for path in check_files:
            with self.subTest(path=path):
                file = os.path.normpath(os.path.join(self.test_tree, path))
                self.assertTrue(os.path.exists(file))
                orig_stats[file] = os.stat(file)

        # generate again, all existed files should be unchanged
        book = Host(self.test_root).books['']
        generator = wsb_cache.StaticSiteGenerator(book, static_index=True)
        for info in generator.run():
            pass

        for path in check_files:
            with self.subTest(path=path):
                file = os.path.normpath(os.path.join(self.test_tree, path))
                self.assertEqual(os.stat(file).st_mtime, orig_stats[file].st_mtime)
                self.assertEqual(os.stat(file).st_size, orig_stats[file].st_size)

    def test_update02(self):
        """Overwrite existing different files"""
        check_files = [
            'icon/toggle.png',
            'icon/search.png',
            'icon/collapse.png',
            'icon/expand.png',
            'icon/external.png',
            'icon/item.png',
            'icon/fclose.png',
            'icon/fopen.png',
            'icon/file.png',
            'icon/note.png',
            'icon/postit.png',
            'index.html',
            'map.html',
            'frame.html',
            'search.html',
            ]

        os.makedirs(os.path.join(self.test_tree, 'icon'))
        orig_stats = {}
        for path in check_files:
            file = os.path.normpath(os.path.join(self.test_tree, path))            
            with open(file, 'wb'):
                pass
            orig_stats[file] = os.stat(file)

        book = Host(self.test_root).books['']
        generator = wsb_cache.StaticSiteGenerator(book, static_index=True)
        for info in generator.run():
            pass

        for path in check_files:
            with self.subTest(path=path):
                file = os.path.normpath(os.path.join(self.test_tree, path))
                self.assertNotEqual(os.stat(file).st_mtime, orig_stats[file].st_mtime)
                self.assertNotEqual(os.stat(file).st_size, orig_stats[file].st_size)

    @mock.patch('webscrapbook.scrapbook.cache.StaticSiteGenerator._generate_page')
    def test_config_filepaths(self, mock_func):
        """Check if special chars in the path are correctly handled."""
        with open(self.test_config, 'w', encoding='UTF-8') as f:
            f.write("""\
[book ""]
top_dir = #top
data_dir = data%中文
tree_dir = tree 中文
index = tree%20%E4%B8%AD%E6%96%87/my%20index.html?id=1#myfrag
""")
        book = Host(self.test_root).books['']
        generator = wsb_cache.StaticSiteGenerator(book, static_index=True)
        for info in generator.run():
            pass

        self.assertEqual(mock_func.call_args_list[0][0], ('index.html', 'static_index.html'))
        self.assertEqual(mock_func.call_args_list[0][1]['data_dir'], '../data%25%E4%B8%AD%E6%96%87/')

        self.assertEqual(mock_func.call_args_list[1][0], ('map.html', 'static_map.html'))
        self.assertEqual(mock_func.call_args_list[1][1]['data_dir'], '../data%25%E4%B8%AD%E6%96%87/')

        self.assertEqual(mock_func.call_args_list[3][0], ('search.html', 'static_search.html'))
        self.assertEqual(mock_func.call_args_list[3][1]['path'], '../')
        self.assertEqual(mock_func.call_args_list[3][1]['data_dir'], 'data%25%E4%B8%AD%E6%96%87/')
        self.assertEqual(mock_func.call_args_list[3][1]['tree_dir'], 'tree%20%E4%B8%AD%E6%96%87/')
        self.assertEqual(mock_func.call_args_list[3][1]['index'], 'tree%20%E4%B8%AD%E6%96%87/my%20index.html?id=1#myfrag')

    @mock.patch('webscrapbook.scrapbook.cache.StaticSiteGenerator._generate_page')
    def test_param_static_index01(self, mock_func):
        """Check if params are passed correctly."""
        book = Host(self.test_root).books['']
        generator = wsb_cache.StaticSiteGenerator(book, static_index=True)
        for info in generator.run():
            pass

        self.assertEqual(mock_func.call_args_list[0][0], ('index.html', 'static_index.html'))
        self.assertEqual(mock_func.call_args_list[0][1]['filename'], 'index')
        self.assertIsInstance(mock_func.call_args_list[0][1]['static_index'], collections.abc.Generator)

    @mock.patch('webscrapbook.scrapbook.cache.StaticSiteGenerator._generate_page')
    def test_param_static_index02(self, mock_func):
        """Check if params are passed correctly."""
        book = Host(self.test_root).books['']
        generator = wsb_cache.StaticSiteGenerator(book, static_index=False)
        for info in generator.run():
            pass

        for i, call in enumerate(mock_func.call_args_list):
            with self.subTest(i=i, file=call[0][0]):
                self.assertNotEqual(call[0][0], 'index.html')
        self.assertEqual(mock_func.call_args_list[0][0], ('map.html', 'static_map.html'))
        self.assertEqual(mock_func.call_args_list[0][1]['filename'], 'map')
        self.assertIsNone(mock_func.call_args_list[0][1]['static_index'])

    @mock.patch('webscrapbook.scrapbook.cache.StaticSiteGenerator._generate_page')
    def test_param_rss01(self, mock_func):
        """rss should be passed."""
        book = Host(self.test_root).books['']
        generator = wsb_cache.StaticSiteGenerator(book, rss=True)
        for info in generator.run():
            pass

        self.assertEqual(mock_func.call_args_list[0][0], ('map.html', 'static_map.html'))
        self.assertTrue(mock_func.call_args_list[0][1]['rss'])

    @mock.patch('webscrapbook.scrapbook.cache.StaticSiteGenerator._generate_page')
    def test_param_rss02(self, mock_func):
        """rss should be passed."""
        book = Host(self.test_root).books['']
        generator = wsb_cache.StaticSiteGenerator(book, rss=False)
        for info in generator.run():
            pass

        self.assertEqual(mock_func.call_args_list[0][0], ('map.html', 'static_map.html'))
        self.assertFalse(mock_func.call_args_list[0][1]['rss'])

    def test_param_locale(self):
        """locale should be passed."""
        book = Host(self.test_root).books['']
        generator = wsb_cache.StaticSiteGenerator(book, static_index=True, locale='ar')
        for info in generator.run():
            pass

        self.assertEqual(generator.template_env.globals['i18n'].lang, 'ar')

    def test_static_index_anchor01(self):
        """Page with index */index.html"""
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "index": "20200101000000000/index#1.html",
    "type": "",
    "source": "http://example.com:8888"
  }
})""")
        with open(os.path.join(self.test_tree, 'toc.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "20200101000000000"
  ]
})""")
        book = Host(self.test_root).books['']

        generator = wsb_cache.StaticSiteGenerator(book, static_index=True)
        for info in generator.run():
            pass

        with open(os.path.join(self.test_tree, 'index.html'), encoding='UTF-8') as fh:
            tree = etree.parse(fh, etree.HTMLParser())
            div = tree.find('/body/div/ul/li/div')

        self.assertEqual(div.find('./a').attrib['href'], '../../20200101000000000/index%231.html')

    def test_static_index_anchor02(self):
        """Page with index *.maff"""
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "index": "20200101000000000#1.maff",
    "type": "",
    "source": "http://example.com:8888"
  }
})""")
        with open(os.path.join(self.test_tree, 'toc.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "20200101000000000"
  ]
})""")
        book = Host(self.test_root).books['']

        generator = wsb_cache.StaticSiteGenerator(book, static_index=True)
        for info in generator.run():
            pass

        with open(os.path.join(self.test_tree, 'index.html'), encoding='UTF-8') as fh:
            tree = etree.parse(fh, etree.HTMLParser())
            div = tree.find('/body/div/ul/li/div')

        self.assertEqual(div.find('./a').attrib['href'], '../../20200101000000000%231.maff')

    def test_static_index_anchor03(self):
        """Page with index *.html"""
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "index": "20200101000000000#1.html",
    "type": "",
    "source": "http://example.com:8888"
  }
})""")
        with open(os.path.join(self.test_tree, 'toc.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "20200101000000000"
  ]
})""")
        book = Host(self.test_root).books['']

        generator = wsb_cache.StaticSiteGenerator(book, static_index=True)
        for info in generator.run():
            pass

        with open(os.path.join(self.test_tree, 'index.html'), encoding='UTF-8') as fh:
            tree = etree.parse(fh, etree.HTMLParser())
            div = tree.find('/body/div/ul/li/div')

        self.assertEqual(div.find('./a').attrib['href'], '../../20200101000000000%231.html')

    def test_static_index_anchor04(self):
        """Page with empty index"""
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "index": "",
    "type": "",
    "source": "http://example.com:8888"
  }
})""")
        with open(os.path.join(self.test_tree, 'toc.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "20200101000000000"
  ]
})""")
        book = Host(self.test_root).books['']

        generator = wsb_cache.StaticSiteGenerator(book, static_index=True)
        for info in generator.run():
            pass

        with open(os.path.join(self.test_tree, 'index.html'), encoding='UTF-8') as fh:
            tree = etree.parse(fh, etree.HTMLParser())
            div = tree.find('/body/div/ul/li/div')

        self.assertIsNone(div.find('./a').attrib.get('href'))

    def test_static_index_anchor05(self):
        """Page without index"""
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "",
    "source": "http://example.com:8888"
  }
})""")
        with open(os.path.join(self.test_tree, 'toc.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "20200101000000000"
  ]
})""")
        book = Host(self.test_root).books['']

        generator = wsb_cache.StaticSiteGenerator(book, static_index=True)
        for info in generator.run():
            pass

        with open(os.path.join(self.test_tree, 'index.html'), encoding='UTF-8') as fh:
            tree = etree.parse(fh, etree.HTMLParser())
            div = tree.find('/body/div/ul/li/div')

        self.assertIsNone(div.find('./a').attrib.get('href'))

    def test_static_index_anchor06(self):
        """Bookmark with source"""
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "bookmark",
    "source": "http://example.com:8888/%231"
  }
})""")
        with open(os.path.join(self.test_tree, 'toc.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "20200101000000000"
  ]
})""")
        book = Host(self.test_root).books['']

        generator = wsb_cache.StaticSiteGenerator(book, static_index=True)
        for info in generator.run():
            pass

        with open(os.path.join(self.test_tree, 'index.html'), encoding='UTF-8') as fh:
            tree = etree.parse(fh, etree.HTMLParser())
            div = tree.find('/body/div/ul/li/div')

        self.assertEqual(div.find('./a').attrib['href'], 'http://example.com:8888/%231')

    def test_static_index_anchor07(self):
        """Bookmark without source and with index"""
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "index": "20200101000000000#1.htm",
    "type": "bookmark"
  }
})""")
        with open(os.path.join(self.test_tree, 'toc.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "20200101000000000"
  ]
})""")
        book = Host(self.test_root).books['']

        generator = wsb_cache.StaticSiteGenerator(book, static_index=True)
        for info in generator.run():
            pass

        with open(os.path.join(self.test_tree, 'index.html'), encoding='UTF-8') as fh:
            tree = etree.parse(fh, etree.HTMLParser())
            div = tree.find('/body/div/ul/li/div')

        self.assertEqual(div.find('./a').attrib['href'], '../../20200101000000000%231.htm')

    def test_static_index_anchor08(self):
        """Bookmark without source and index"""
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "bookmark"
  }
})""")
        with open(os.path.join(self.test_tree, 'toc.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "20200101000000000"
  ]
})""")
        book = Host(self.test_root).books['']

        generator = wsb_cache.StaticSiteGenerator(book, static_index=True)
        for info in generator.run():
            pass

        with open(os.path.join(self.test_tree, 'index.html'), encoding='UTF-8') as fh:
            tree = etree.parse(fh, etree.HTMLParser())
            div = tree.find('/body/div/ul/li/div')

        self.assertIsNone(div.find('./a').attrib.get('href'))

    def test_static_index_anchor09(self):
        """Folder should not have href anyway"""
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "index": "20200101000000000/index#1.html",
    "type": "folder"
  }
})""")
        with open(os.path.join(self.test_tree, 'toc.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "20200101000000000"
  ]
})""")
        book = Host(self.test_root).books['']

        generator = wsb_cache.StaticSiteGenerator(book, static_index=True)
        for info in generator.run():
            pass

        with open(os.path.join(self.test_tree, 'index.html'), encoding='UTF-8') as fh:
            tree = etree.parse(fh, etree.HTMLParser())
            div = tree.find('/body/div/ul/li/div')

        self.assertIsNone(div.find('./a').attrib.get('href'))

    def test_static_index_icon01(self):
        """Icon with absolute path."""
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "",
    "index": "20200101000000000/index.html",
    "icon": "http://example.com/favicon%231.ico"
  }
})""")
        with open(os.path.join(self.test_tree, 'toc.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "20200101000000000"
  ]
})""")
        book = Host(self.test_root).books['']

        generator = wsb_cache.StaticSiteGenerator(book, static_index=True)
        for info in generator.run():
            pass

        with open(os.path.join(self.test_tree, 'index.html'), encoding='UTF-8') as fh:
            tree = etree.parse(fh, etree.HTMLParser())
            div = tree.find('/body/div/ul/li/div')

        self.assertEqual(div.find('./a/img').attrib['src'], 'http://example.com/favicon%231.ico')

    def test_static_index_icon02(self):
        """Icon with index */index.html"""
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "",
    "index": "20200101000000000/index.html",
    "icon": "favicon%231.ico"
  }
})""")
        with open(os.path.join(self.test_tree, 'toc.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "20200101000000000"
  ]
})""")
        book = Host(self.test_root).books['']

        generator = wsb_cache.StaticSiteGenerator(book, static_index=True)
        for info in generator.run():
            pass

        with open(os.path.join(self.test_tree, 'index.html'), encoding='UTF-8') as fh:
            tree = etree.parse(fh, etree.HTMLParser())
            div = tree.find('/body/div/ul/li/div')

        self.assertEqual(div.find('./a/img').attrib['src'], '../../20200101000000000/favicon%231.ico')

    def test_static_index_icon03(self):
        """Icon with index *.maff"""
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "",
    "index": "20200101000000000.maff",
    "icon": ".wsb/tree/favicon/0123456789abcdef0123456789abcdef01234567.ico"
  }
})""")
        with open(os.path.join(self.test_tree, 'toc.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "20200101000000000"
  ]
})""")
        book = Host(self.test_root).books['']

        generator = wsb_cache.StaticSiteGenerator(book, static_index=True)
        for info in generator.run():
            pass

        with open(os.path.join(self.test_tree, 'index.html'), encoding='UTF-8') as fh:
            tree = etree.parse(fh, etree.HTMLParser())
            div = tree.find('/body/div/ul/li/div')

        self.assertEqual(div.find('./a/img').attrib['src'], '../../.wsb/tree/favicon/0123456789abcdef0123456789abcdef01234567.ico')

    def test_static_index_icon04(self):
        """Icon with no index"""
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "",
    "icon": ".wsb/tree/favicon/0123456789abcdef0123456789abcdef01234567.ico"
  }
})""")
        with open(os.path.join(self.test_tree, 'toc.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "20200101000000000"
  ]
})""")
        book = Host(self.test_root).books['']

        generator = wsb_cache.StaticSiteGenerator(book, static_index=True)
        for info in generator.run():
            pass

        with open(os.path.join(self.test_tree, 'index.html'), encoding='UTF-8') as fh:
            tree = etree.parse(fh, etree.HTMLParser())
            div = tree.find('/body/div/ul/li/div')

        self.assertEqual(div.find('./a/img').attrib['src'], '../../.wsb/tree/favicon/0123456789abcdef0123456789abcdef01234567.ico')

    def test_static_index_icon05(self):
        """Default icon (empty icon)"""
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "",
    "icon": ""
  }
})""")
        with open(os.path.join(self.test_tree, 'toc.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "20200101000000000"
  ]
})""")
        book = Host(self.test_root).books['']

        generator = wsb_cache.StaticSiteGenerator(book, static_index=True)
        for info in generator.run():
            pass

        with open(os.path.join(self.test_tree, 'index.html'), encoding='UTF-8') as fh:
            tree = etree.parse(fh, etree.HTMLParser())
            div = tree.find('/body/div/ul/li/div')

        self.assertEqual(div.find('./a/img').attrib['src'], 'icon/item.png')

    def test_static_index_icon06(self):
        """Default icon (no icon)"""
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": ""
  }
})""")
        with open(os.path.join(self.test_tree, 'toc.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "20200101000000000"
  ]
})""")
        book = Host(self.test_root).books['']

        generator = wsb_cache.StaticSiteGenerator(book, static_index=True)
        for info in generator.run():
            pass

        with open(os.path.join(self.test_tree, 'index.html'), encoding='UTF-8') as fh:
            tree = etree.parse(fh, etree.HTMLParser())
            div = tree.find('/body/div/ul/li/div')

        self.assertEqual(div.find('./a/img').attrib['src'], 'icon/item.png')

    def test_static_index_icon07(self):
        """Default icon for folder"""
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "folder"
  }
})""")
        with open(os.path.join(self.test_tree, 'toc.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "20200101000000000"
  ]
})""")
        book = Host(self.test_root).books['']

        generator = wsb_cache.StaticSiteGenerator(book, static_index=True)
        for info in generator.run():
            pass

        with open(os.path.join(self.test_tree, 'index.html'), encoding='UTF-8') as fh:
            tree = etree.parse(fh, etree.HTMLParser())
            div = tree.find('/body/div/ul/li/div')

        self.assertEqual(div.find('./a/img').attrib['src'], 'icon/fclose.png')

    def test_static_index_icon08(self):
        """Default icon for file"""
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "file"
  }
})""")
        with open(os.path.join(self.test_tree, 'toc.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "20200101000000000"
  ]
})""")
        book = Host(self.test_root).books['']

        generator = wsb_cache.StaticSiteGenerator(book, static_index=True)
        for info in generator.run():
            pass

        with open(os.path.join(self.test_tree, 'index.html'), encoding='UTF-8') as fh:
            tree = etree.parse(fh, etree.HTMLParser())
            div = tree.find('/body/div/ul/li/div')

        self.assertEqual(div.find('./a/img').attrib['src'], 'icon/file.png')

    def test_static_index_icon09(self):
        """Default icon for image"""
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "image"
  }
})""")
        with open(os.path.join(self.test_tree, 'toc.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "20200101000000000"
  ]
})""")
        book = Host(self.test_root).books['']

        generator = wsb_cache.StaticSiteGenerator(book, static_index=True)
        for info in generator.run():
            pass

        with open(os.path.join(self.test_tree, 'index.html'), encoding='UTF-8') as fh:
            tree = etree.parse(fh, etree.HTMLParser())
            div = tree.find('/body/div/ul/li/div')

        self.assertEqual(div.find('./a/img').attrib['src'], 'icon/file.png')

    def test_static_index_icon10(self):
        """Default icon for note"""
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "note"
  }
})""")
        with open(os.path.join(self.test_tree, 'toc.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "20200101000000000"
  ]
})""")
        book = Host(self.test_root).books['']

        generator = wsb_cache.StaticSiteGenerator(book, static_index=True)
        for info in generator.run():
            pass

        with open(os.path.join(self.test_tree, 'index.html'), encoding='UTF-8') as fh:
            tree = etree.parse(fh, etree.HTMLParser())
            div = tree.find('/body/div/ul/li/div')

        self.assertEqual(div.find('./a/img').attrib['src'], 'icon/note.png')

    def test_static_index_icon11(self):
        """Default icon for postit"""
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "postit"
  }
})""")
        with open(os.path.join(self.test_tree, 'toc.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "20200101000000000"
  ]
})""")
        book = Host(self.test_root).books['']

        generator = wsb_cache.StaticSiteGenerator(book, static_index=True)
        for info in generator.run():
            pass

        with open(os.path.join(self.test_tree, 'index.html'), encoding='UTF-8') as fh:
            tree = etree.parse(fh, etree.HTMLParser())
            div = tree.find('/body/div/ul/li/div')

        self.assertEqual(div.find('./a/img').attrib['src'], 'icon/postit.png')

    def test_static_index_title01(self):
        """Item without title (use ID)."""
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": ""
  }
})""")
        with open(os.path.join(self.test_tree, 'toc.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "20200101000000000"
  ]
})""")
        book = Host(self.test_root).books['']

        generator = wsb_cache.StaticSiteGenerator(book, static_index=True)
        for info in generator.run():
            pass

        with open(os.path.join(self.test_tree, 'index.html'), encoding='UTF-8') as fh:
            tree = etree.parse(fh, etree.HTMLParser())
            div = tree.find('/body/div/ul/li/div')

        self.assertEqual(
            etree.tostring(div, encoding='unicode', with_tail=False),
            '<div><a><img src="icon/item.png" alt="" loading="lazy"/>20200101000000000</a></div>',
            )

    def test_static_index_title02(self):
        """Item with title."""
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "",
    "title": "My title 中文"
  }
})""")
        with open(os.path.join(self.test_tree, 'toc.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "20200101000000000"
  ]
})""")
        book = Host(self.test_root).books['']

        generator = wsb_cache.StaticSiteGenerator(book, static_index=True)
        for info in generator.run():
            pass

        with open(os.path.join(self.test_tree, 'index.html'), encoding='UTF-8') as fh:
            tree = etree.parse(fh, etree.HTMLParser())
            div = tree.find('/body/div/ul/li/div')

        self.assertEqual(
            etree.tostring(div, encoding='unicode', with_tail=False),
            '<div><a><img src="icon/item.png" alt="" loading="lazy"/>My title 中文</a></div>',
            )

    def test_static_index_title03(self):
        """Separator without title."""
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "separator"
  }
})""")
        with open(os.path.join(self.test_tree, 'toc.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "20200101000000000"
  ]
})""")
        book = Host(self.test_root).books['']

        generator = wsb_cache.StaticSiteGenerator(book, static_index=True)
        for info in generator.run():
            pass

        with open(os.path.join(self.test_tree, 'index.html'), encoding='UTF-8') as fh:
            tree = etree.parse(fh, etree.HTMLParser())
            div = tree.find('/body/div/ul/li/div')

        self.assertEqual(
            etree.tostring(div, encoding='unicode', with_tail=False),
            '<div><fieldset><legend>\xA0\xA0</legend></fieldset></div>',
            )

    def test_static_index_title04(self):
        """Separator with title."""
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "separator",
    "title": "My sep 中文"
  }
})""")
        with open(os.path.join(self.test_tree, 'toc.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "20200101000000000"
  ]
})""")
        book = Host(self.test_root).books['']

        generator = wsb_cache.StaticSiteGenerator(book, static_index=True)
        for info in generator.run():
            pass

        with open(os.path.join(self.test_tree, 'index.html'), encoding='UTF-8') as fh:
            tree = etree.parse(fh, etree.HTMLParser())
            div = tree.find('/body/div/ul/li/div')

        self.assertEqual(
            etree.tostring(div, encoding='unicode', with_tail=False),
            '<div><fieldset><legend>\xA0My sep 中文\xA0</legend></fieldset></div>',
            )

if __name__ == '__main__':
    unittest.main()
