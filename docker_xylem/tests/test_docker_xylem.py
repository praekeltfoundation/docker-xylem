
from twisted.trial import unittest

from twisted.internet import defer


class Test(unittest.TestCase):

    @defer.inlineCallbacks
    def test_things(self):
        pass

