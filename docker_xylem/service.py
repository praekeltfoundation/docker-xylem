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

        self.current = {}

    def xylem_request(self, queue, call, data):
        return utils.HTTPRequest(timeout=60).getJson(
            'http://%s:%s/queues/%s/wait/%s' % (
                self.xylem_host, self.xylem_port, queue, call
            ),
            method='POST',
            data=json.dumps(data),
        )

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
    def mount_volume(self, request, data):
        name = data['Name']
        path = os.path.join(self.mount_path, name)

        try:
            yield self._mount_fs(self.xylem_host, name, path)

            if not name in self.current:
                self.current[name] = path

            defer.returnValue({
                "Mountpoint": path,
                "Err": None
            })

        except Exception, e:
            defer.returnValue({"Err": repr(e)})

    @defer.inlineCallbacks
    def unmount_volume(self, request, data):
        name = data['Name']
        path = os.path.join(self.mount_path, name)

        try:
            yield self._umount_fs(path)
            defer.returnValue({"Err": None})

        except Exception, e:
            defer.returnValue({"Err": repr(e)})

    def get_volume_path(self, request, data):
        name = data['Name']
        path = os.path.join(self.mount_path, name)
        return {
            "Mountpoint": path,
            "Err": None
        }

    def remove_volume(self, request, data):
        # FIXME: This probably isn't supposed to do nothing.
        name = data['Name']

        return {"Err": None}

    @defer.inlineCallbacks
    def create_volume(self, request, data):
        name = data['Name']

        result = yield self.xylem_request('gluster', 'createvolume', {
            'name': name
        })

        if not result['result']['running']:
            err = "Error creating volume %s" % name
        else:
            err = None

        defer.returnValue({"Err": err})

    def get_volume(self, request, data):
        name = data['Name']

        if name in self.current:
            return {
                'Volume': {
                    'Name': name,
                    'Mountpoint': self.current[name]
                }, 
                'Err': None
            }
        else:
            return {'Err': 'No mounted volume'}

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
