import json
import os
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
        self.basepath = os.getcwd()

        self.service = DockerService({
            'host': 'localhost',
            'mount_path': self.basepath
        })

        self.service.xylem_request = lambda *a: defer.maybeDeferred(
            self.xylem_request, *a)

        self.service._mount_fs = lambda *a: defer.maybeDeferred(
            self.mountfs, *a)

        self.service._umount_fs = lambda *a: defer.maybeDeferred(
            self.mountfs, *a)

        mountdata = """rootfs / rootfs rw 0 0
sysfs /sys sysfs rw,nosuid,nodev,noexec,relatime 0 0
proc /proc proc rw,nosuid,nodev,noexec,relatime 0 0
udev /dev devtmpfs rw,relatime,size=4004172k,nr_inodes=1001043,mode=755 0 0
devpts /dev/pts devpts rw,nosuid,noexec,relatime,gid=5,mode=620 0 0
tmpfs /run tmpfs rw,nosuid,noexec,relatime,size=803564k,mode=755 0 0
/dev/disk/by-uuid/06879afa-04bf-4bbd-8dc1-1c6380a2b962 / ext4 defaults 0 0
none /run/user tmpfs rw,nosuid,nodev,noexec,relatime,size=102400k,mode=755 0 0
cgroup /sys/fs/cgroup/cpuset cgroup rw,relatime,cpuset 0 0
none /sys/fs/pstore pstore rw,relatime 0 0
cgroup /sys/fs/cgroup/hugetlb cgroup rw,relatime,hugetlb 0 0
/dev/md0 /media xfs rw,noatime,attr2,inode64,noquota 0 0
systemd /sys/fs/cgroup/systemd cgroup rw,nosuid,nodev,noexec,name=systemd 0 0
test:/seed %s fuse.glusterfs defaults 0 0\n"""

        self.service._get_proc_mounts = lambda: mountdata % os.path.join(
            self.basepath, 'seed')


    def _get_path(self, name):
        return os.path.join(self.basepath, 'seed', name)

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
    def test_remove(self):
        result = yield self.service._route_request(FakeRequest(
            '/VolumeDriver.Remove', {'Name': 'testvol', 'Opts': {}}))

        self.assertEquals(result['Err'], None)

    @defer.inlineCallbacks
    def test_mount(self):
        result = yield self.service._route_request(FakeRequest(
            '/VolumeDriver.Mount', {'Name': 'testvol', 'Opts': {}}))

        self.assertEquals(result['Mountpoint'], self._get_path('testvol'))
        self.assertEquals(result['Err'], None)

        result = yield self.service._route_request(FakeRequest(
            '/VolumeDriver.Unmount', {'Name': 'testvol'}))

        self.assertEquals(result['Err'], None)

    @defer.inlineCallbacks
    def test_path(self):
        result = yield self.service._route_request(FakeRequest(
            '/VolumeDriver.Path', {'Name': 'testvol'}))

        self.assertEquals(result['Mountpoint'], self._get_path('testvol'))

    @defer.inlineCallbacks
    def test_get(self):
        yield self.service._route_request(FakeRequest(
            '/VolumeDriver.Mount', {'Name': 'testvol', 'Opts': {}}))

        result = yield self.service._route_request(FakeRequest(
            '/VolumeDriver.Get', {'Name': 'testvol'}))

        self.assertEquals(result['Err'], None)

    @defer.inlineCallbacks
    def test_list(self):
        yield self.service._route_request(FakeRequest(
            '/VolumeDriver.Mount', {'Name': 'testvol', 'Opts': {}}))

        result = yield self.service._route_request(FakeRequest(
            '/VolumeDriver.List', {}))

        self.assertEquals(result['Err'], None)
        self.assertEquals(result['Volumes'][0]['Name'], 'testvol')

    def test_mount_check(self):
        mount = self.service._check_mount('seed')
        self.assertTrue(mount)
