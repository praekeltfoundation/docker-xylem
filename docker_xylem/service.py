import time
import exceptions
import json
import cgi
import datetime

from twisted.application import service
from twisted.internet import task, reactor, protocol, defer
from twisted.web import server, resource
from twisted.python import log

from docker_xylem import utils

class DockerService(resource.Resource):
    isLeaf = True
    addSlash = True

    def __init__(self):
        self.requestRouter = {
            '/Plugin.Activate': self.plugin_activate,
            '/VolumeDriver.Create': self.create_volume,
        }

    @defer.inlineCallbacks
    def create_volume(self, request, data):
        name = data['Name']

        cv = yield utils.HTTPRequest().getJson(
            'http://%s:/queues/gluster/wait/createvolume' % self.xylem_host,
            method='POST',
            data=json.dumps({'name': name})
        )

    def plugin_activate(self, request, data):
        return {
            'Implements': ['VolumeDriver']
        }

    def completeCall(self, response, request):
        # Render the json response from call
        response = json.dumps(response)
        request.write(response)
        request.finish()

    def render_POST(self, request):
        request.setHeader("content-type", "application/json")

        print request.path


        data = json.loads(cgi.escape(request.content.read()))

        method = self.requestRouter.get(request.path)

        if not method:
            return "Not Implemented"
            
        d = defer.maybeDeferred(method, request, data)

        d.addCallback(self.completeCall, request)

        return server.NOT_DONE_YET
