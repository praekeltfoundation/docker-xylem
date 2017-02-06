import os
import json
import cgi

from twisted.internet import defer
from twisted.web import server, resource

from docker_xylem import utils
from docker_xylem.compat import Logger


class DockerService(resource.Resource):
    isLeaf = True
    addSlash = True
    log = Logger()

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
            '/VolumeDriver.Capabilities': self.capabilities,
        }

        self.xylem_host = config['host']
        self.xylem_port = config.get('port', 7701)
        self.mount_path = config.get(
            'mount_path',
            '/var/lib/docker-xylem/volumes'
        )
        self.old_paths = config.get('old_mount_paths', [])
        self.current = {}

    def xylem_request(self, queue, call, data):
        self.log.info(
            'Xylem HTTP request to create volume {name}',
            name=data['name']
        )
        return utils.HTTPRequest(timeout=60).getJson(
            'http://%s:%s/queues/%s/wait/%s' % (
                self.xylem_host, self.xylem_port, queue, call
            ),
            method='POST',
            data=json.dumps(data),
        )

    def _fork(self, *args, **kw):
        return utils.fork(*args, **kw)

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

        out, err, code = yield self._fork('/bin/mount', args=(
            '-t', 'glusterfs', '%s:/%s' % (server, volume), dst))

        if code > 0:
            raise Exception(err)

        else:
            defer.returnValue(True)

    @defer.inlineCallbacks
    def _umount_fs(self, path):
        """ Mount a gluster filesystem on this host
        """

        out, err, code = yield self._fork('/bin/umount', args=(path,))

        if code > 0:

            if (path in err) and ("not mounted" in err):
                # Return false is not mounted
                self.log.warn('Volume {path} is not mounted', path=path)
                defer.returnValue(False)
            else:
                # Raise an exception for any other error
                raise Exception(err)
        else:
            # Return true is mounted
            self.log.info('Successfully unmounted {path}', path=path)
            defer.returnValue(True)

    @defer.inlineCallbacks
    def mount_volume(self, request, data):
        name = data['Name']
        path = os.path.join(self.mount_path, name)

        try:
            yield self._mount_fs(self.xylem_host, name, path)

            if name not in self.current:
                self.current[name] = path
            self.log.info(
                'Successfully mounted volume {name}. Mount path:\"{path}\"',
                name=name, path=path
            )
            defer.returnValue({
                "Mountpoint": path,
                "Err": None
            })

        except Exception, e:
            self.log.error(
                'Error mounting {name}. \"{e.message}\"',
                name=name, e=e
            )
            defer.returnValue({"Err": repr(e)})

    @defer.inlineCallbacks
    def unmount_volume(self, request, data):
        name = data['Name']
        try:
            paths = self.get_paths(name)
            for path in paths:
                self.log.info(
                    'Attemptting to unmount {name} from \"{path}\"',
                    name=name, path=path
                )
                yield self._umount_fs(path)

            self.log.info(
                'Volume {name} unmounted from all mount paths.',
                name=name
            )
            defer.returnValue({"Err": None})

        except Exception, e:
            self.log.error(
                'Error unmounting volume {name}. \"{e.message}\"',
                name=name, e=e
            )
            defer.returnValue({"Err": repr(e)})

    def get_paths(self, name):
        """
        Function to return an array of mount paths
        :param name: Name of volume
        :return: list of possible paths for given volume name
        """
        paths = [os.path.join(path, name) for path in self.old_paths]
        paths.append(os.path.join(self.mount_path, name))
        return paths

    def get_volume_path(self, request, data):
        name = data['Name']
        path = os.path.join(self.mount_path, name)
        return {
            "Mountpoint": path,
            "Err": None
        }

    def remove_volume(self, request, data):
        # FIXME: This probably isn't supposed to do nothing.
        return {"Err": None}

    @defer.inlineCallbacks
    def create_volume(self, request, data):
        name = data['Name']

        result = yield self.xylem_request('gluster', 'createvolume', {
            'name': name
        })

        if not result['result']['running']:
            self.log.error(
                'Error creating volume {name} with ID: \"{id}\"',
                name=name, id=result['result'][id]
            )
            err = "Error creating volume %s" % name
        else:
            err = None

        self.log.info('Successfully created the volume {name}.', name=name)
        defer.returnValue({"Err": err})

    def get_volume(self, request, data):
        name = data['Name']

        if name in self.current:
            return {
                'Volume': {
                    'Name': name,
                    'Mountpoint': self.current[name],
                    'Status': {}
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

    def capabilities(self, request, data):
        return {
            "Capabilities": {
                "Scope": "global"
            }
        }

    def plugin_activate(self, request, data):
        self.log.info('Docker-Xylem plugin activated.')
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
            self.log.warn(
                '{request.path} is not implemented by plugin.',
                request=request
            )
            return "Not Implemented"
        self.log.info(
            '{request.path} called. data={data}',
            request=request, data=data
        )
        return defer.maybeDeferred(method, request, data)

    def render_POST(self, request):
        request.setHeader("content-type", "application/json")

        self.log.info('request.path', request=request)

        self._route_request(request).addCallback(self.completeCall, request)

        return server.NOT_DONE_YET
