import yaml
import os

from zope.interface import implements
 
from twisted.python import usage
from twisted.plugin import IPlugin
from twisted.application.service import IServiceMaker
from twisted.application import internet
from twisted.web import server

from docker_xylem import service
 
class Options(usage.Options):
    optParameters = [
        ["config", "c", "xylem-plugin.yml", "Config file"],
    ]

class DockerServiceMaker(object):
    implements(IServiceMaker, IPlugin)
    tapname = "docker_xylem"
    description = "A docker plugin service for xylem"
    options = Options
 
    def makeService(self, options):
        config = yaml.load(open(options['config']))

        socket = config.get('socket', "/run/docker/plugins/xylem.sock")

        sock_path = os.path.dirname(socket)

        if not os.path.exists(sock_path):
            os.makedirs(sock_path)

        return internet.UNIXServer(socket,
            server.Site(service.DockerService(config)))
 
serviceMaker = DockerServiceMaker()
