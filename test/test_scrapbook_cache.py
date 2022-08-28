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

if __name__ == '__main__':
    unittest.main()
