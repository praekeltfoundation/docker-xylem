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
            'mount_path': '/tmp/docker-xylem-test',
            'old_mount_paths': [
                '/some/old/path', '/another/random/old/path',
                '/just/one/more/wont/hurt'
            ]
        })

        self.service.xylem_request = lambda *a: defer.maybeDeferred(
            self.xylem_request, *a)

        self.service._fork = self.fork

    def fork(self, *args, **kw):
        """
        Method to replace service._fork for testing purposes
        """
        return defer.succeed(("", "", 0))

    def fork_unmount_err(self, *args, **kw):
        """Fork to simulate unmount error"""
        return defer.succeed(("", "%s is not mounted" % kw['args'][0], 32))

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
    def test_remove(self):
        result = yield self.service._route_request(FakeRequest(
            '/VolumeDriver.Remove', {'Name': 'testvol', 'Opts': {}}))

        self.assertEquals(result['Err'], None)

    @defer.inlineCallbacks
    def test_mount(self):
        result = yield self.service._route_request(FakeRequest(
            '/VolumeDriver.Mount', {'Name': 'testvol', 'Opts': {}}))

        self.assertEquals(
            result['Mountpoint'],
            '/tmp/docker-xylem-test/testvol'
        )
        self.assertEquals(result['Err'], None)

        result = yield self.service._route_request(FakeRequest(
            '/VolumeDriver.Unmount', {'Name': 'testvol'}))

        self.assertEquals(result['Err'], None)

    @defer.inlineCallbacks
    def test_path(self):
        result = yield self.service._route_request(FakeRequest(
            '/VolumeDriver.Path', {'Name': 'testvol'}))

        self.assertEquals(
            result['Mountpoint'],
            '/tmp/docker-xylem-test/testvol'
        )

    @defer.inlineCallbacks
    def test_get(self):
        yield self.service._route_request(FakeRequest(
            '/VolumeDriver.Mount', {'Name': 'testvol', 'Opts': {}}))

        result = yield self.service._route_request(FakeRequest(
            '/VolumeDriver.Get', {'Name': 'testvol'}))

        self.assertEquals(result['Err'], None)
        self.assertEquals(result['Volume']['Status'], {})

    @defer.inlineCallbacks
    def test_list(self):
        yield self.service._route_request(FakeRequest(
            '/VolumeDriver.Mount', {'Name': 'testvol', 'Opts': {}}))

        result = yield self.service._route_request(FakeRequest(
            '/VolumeDriver.List', {}))

        self.assertEquals(result['Err'], None)
        self.assertEquals(result['Volumes'][0]['Name'], 'testvol')

    @defer.inlineCallbacks
    def test_capabilities(self):
        """
        Test for /VolumeDriver.Capabilities
        VolumeDriver.Capabilities always returns {'Scope': 'global'}.
        """
        result = yield self.service._route_request(FakeRequest(
            '/VolumeDriver.Capabilities', {}))

        self.assertEquals(result['Capabilities']['Scope'], 'global')

    @defer.inlineCallbacks
    def test_unmount_unchanged_path(self):
        """
        Test for /Volume.Unmount when the mount path has NOT been changed
        """
        # Check if old mount paths were read correctly
        self.assertFalse(len(self.service.old_paths) == 0)

        data = {'Name': 'testvol', 'ID': 'RANDOM_ID'}
        yield self.service._route_request(FakeRequest(
            '/VolumeDriver.Mount', data))

        path = self.service.get_volume_path(None, data)['Mountpoint']
        result1 = yield self.service._umount_fs(path)
        result2 = yield self.service._route_request(FakeRequest(
            '/VolumeDriver.Unmount', data))

        self.assertEquals(result1, True)
        self.assertEquals(result2['Err'], None)

    @defer.inlineCallbacks
    def test_unmount_changed_path(self):
        """
        Test for /Volume.Unmount when the mount path HAS BEEN changed
        """

        # Check if old mount paths were read correctly
        self.assertFalse(len(self.service.old_paths) == 0)

        data = {'Name': 'testvol', 'ID': 'RANDOM_ID'}
        yield self.service._route_request(FakeRequest(
            '/VolumeDriver.Mount', data))
        self.service.mount_path = '/var/lib/docker/volumes'
        path = self.service.get_volume_path(None, data)['Mountpoint']

        # Replace the fork function to create an unmount error
        self.service._fork = self.fork_unmount_err

        result1 = yield self.service._umount_fs(path)
        result2 = yield self.service._route_request(FakeRequest(
            '/VolumeDriver.Unmount', data))

        self.assertEquals(result1, False)
        self.assertEquals(result2['Err'], None)

        # Restore the old test fork function?
        self.service._fork = self.fork
