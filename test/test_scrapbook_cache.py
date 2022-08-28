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

if __name__ == '__main__':
    unittest.main()
