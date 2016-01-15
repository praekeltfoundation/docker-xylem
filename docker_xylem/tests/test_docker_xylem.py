import json
from StringIO import StringIO

from twisted.trial import unittest
from twisted.internet import defer

from docker_xylem.service import DockerService

class FakeRequest(object):
    def __init__(self, path, data):
        self.content = StringIO(json.dumps(data))
        self.path = path

class Test(unittest.TestCase):

    def setUp(self):
        self.service = DockerService({
            'host': 'localhost',
            'mounts': '/mnt'
        })

        self.service.xylem_request = lambda *a: defer.maybeDeferred(
            self.xylem_request, *a)

        self.service._mount_fs = lambda *a: defer.maybeDeferred(
            self.mountfs, *a)

    def mountfs(self, *a):
        pass

    def xylem_request(self, queue, call, data):
        if call == 'createvolume':
            return {"result": {
                "bricks": ["test:/data/testvol"],
                "running": True,
                "id": "8bda3daa-4fe8-4021-8acd-4100ea2833fb"
            }}

        return {}

    @defer.inlineCallbacks
    def test_activate(self):
        
        result = yield self.service._route_request(FakeRequest(
            '/Plugin.Activate', {}))

        self.assertIn('Implements', result)

    @defer.inlineCallbacks
    def test_create(self):
        result = yield self.service._route_request(FakeRequest(
            '/VolumeDriver.Create', {'Name': 'testvol', 'Opts': {}}))

        self.assertEquals(result['Err'], None)

    @defer.inlineCallbacks
    def test_mount(self):
        result = yield self.service._route_request(FakeRequest(
            '/VolumeDriver.Mount', {'Name': 'testvol', 'Opts': {}}))

        self.assertEquals(result['Mountpoint'], '/mnt/testvol')

    @defer.inlineCallbacks
    def test_path(self):
        result = yield self.service._route_request(FakeRequest(
            '/VolumeDriver.Path', {'Name': 'testvol', 'Opts': {}}))

        self.assertEquals(result['Mountpoint'], '/mnt/testvol')


