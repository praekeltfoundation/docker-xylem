import os
import json
import cgi

from twisted.application import service
from twisted.internet import defer
from twisted.web import server, resource
from twisted.python import log

from docker_xylem import utils

class DockerService(resource.Resource):
    isLeaf = True
    addSlash = True

    def __init__(self, config):
        self.requestRouter = {
            '/Plugin.Activate': self.plugin_activate,
            '/VolumeDriver.Create': self.create_volume,
            '/VolumeDriver.Remove': self.remove_volume,
            '/VolumeDriver.Mount': self.mount_volume,
            '/VolumeDriver.Path': self.get_volume_path,
            '/VolumeDriver.Unmount': self.unmount_volume,
            '/VolumeDriver.Get': self.get_volume,
            '/VolumeDriver.List': self.list_volumes,
        }
        
        self.xylem_host = config['host']
        self.xylem_port = config.get('port', 7701)
        self.mount_path = config.get('mount_path', '/var/lib/docker/volumes')
        self.volume_name = config.get('volume_name', 'seed')

        self.volume_path = os.path.join(self.mount_path, self.volume_name)

        self.current = {}

    def xylem_request(self, queue, call, data):
        return utils.HTTPRequest(timeout=60).getJson(
            'http://%s:%s/queues/%s/wait/%s' % (
                self.xylem_host, self.xylem_port, queue, call
            ),
            method='POST',
            data=json.dumps(data),
        )

    def _get_path(self, name):
        return os.path.join(self.volume_path, name)

    def _get_proc_mounts(self):
        return open('/proc/mounts', 'rt').read()

    def _check_mount(self, name):
        path = os.path.join(self.mount_path, name)

        mounts = self._get_proc_mounts()

        for l in mounts.split('\n'):
            if l.strip():
                src, mount, typ, opts, dump, fpass = l.strip().split()
                if mount == path:
                    return True

        return False

    @defer.inlineCallbacks
    def _mount_fs(self, server, volume, dst):
        """ Mount a gluster filesystem on this host
        """

        try:
            os.makedirs(dst)
        except os.error, e:
            # Raise any error except path exists
            if e.errno != 17:
                raise e

        out, err, code = yield utils.fork('/bin/mount', args=(
            '-t', 'glusterfs', '%s:/%s' % (server, volume), dst))

        if code > 0:
            raise Exception(err)

        else:
            defer.returnValue(True)

    @defer.inlineCallbacks
    def _umount_fs(self, path):
        """ Mount a gluster filesystem on this host
        """

        out, err, code = yield utils.fork('/bin/umount', args=(path,))

        if code > 0:
            if "%s is not mounted" % path in err:
                defer.returnValue(True)
            else:
                raise Exception(err)
        else:
            defer.returnValue(True)

    @defer.inlineCallbacks
    def check_base_mount(self):
        if not self._check_mount(self.volume_name):
            result = yield self.xylem_request('gluster', 'createvolume', {
                        'name': self.volume_name})

            if not result['result']['running']:
                raise Exception("Error starting volume %s" % self.volume_name)

            yield self._mount_fs(self.xylem_host, self.volume_name,
                self.volume_path)

    @defer.inlineCallbacks
    def mount_volume(self, request, data):
        name = data['Name']
        path = self._get_path(name)

        try:
            yield self.check_base_mount()

            if not os.path.exists(path):
                os.makedirs(path)

            if not name in self.current:
                self.current[name] = path

            defer.returnValue({
                "Mountpoint": path,
                "Err": None
            })
        except Exception, e:
            defer.returnValue({"Err": repr(e)})

    def unmount_volume(self, request, data):
        name = data['Name']

        if name in self.current:
            del self.current[name]
        else:
            log.msg("%s not mounted" % name)

        return {"Err": None}

    def get_volume_path(self, request, data):
        name = data['Name']
        path = self._get_path(name)
        return {
            "Mountpoint": path,
            "Err": None
        }

    def remove_volume(self, request, data):
        return {"Err": None}

    @defer.inlineCallbacks
    def create_volume(self, request, data):
        name = data['Name']
        path = self._get_path(name)
        err = None
        try:
            yield self.check_base_mount()
        except Exception, e:
            defer.returnValue({"Err": str(e)})

        if not os.path.exists(path):
            try:
                os.makedirs(path)
            except Exception, e:
                err = "Failed to create volume %s: %s" % (name, e)

        defer.returnValue({"Err": err})

    def get_volume(self, request, data):
        name = data['Name']

        return {
            'Volume': {
                'Name': name,
                'Mountpoint': self._get_path(name)
            }, 
            'Err': None
        }

    def list_volumes(self, request, data):
        vols = []

        for k, v in self.current.items():
            vols.append({
                'Name': k,
                'Mountpoint': v
            })

        return {'Volumes': vols, 'Err': None}
    
    def plugin_activate(self, request, data):
        return {
            'Implements': ['VolumeDriver']
        }

    def completeCall(self, response, request):
        # Render the json response from call
        response = json.dumps(response)
        log.msg(response)

        request.write(response)
        request.finish()

    def _route_request(self, request):
        cnt = request.content.read()
        if cnt:
            data = json.loads(cgi.escape(cnt))
        else:
            data = None

        method = self.requestRouter.get(request.path)

        if not method:
            return "Not Implemented"
            
        return defer.maybeDeferred(method, request, data)

    def render_POST(self, request):
        request.setHeader("content-type", "application/json")

        log.msg(request.path)

        self._route_request(request).addCallback(self.completeCall, request)

        return server.NOT_DONE_YET
