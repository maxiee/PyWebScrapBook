"""Generator of fulltext cache and/or static site pages.
"""
from collections import UserDict

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

