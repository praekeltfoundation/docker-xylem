from zope.interface import implements
 
from twisted.python import usage
from twisted.plugin import IPlugin
from twisted.application.service import IServiceMaker
from twisted.application import internet
from twisted.web import server

from docker_xylem import service
 
class Options(usage.Options):
    optParameters = [
        ["socket", "s", "/run/docker/plugins/xylem.sock", "Socket path"],
    ]
 
class DockerServiceMaker(object):
    implements(IServiceMaker, IPlugin)
    tapname = "docker_xylem"
    description = "A docker plugin service for xylem"
    options = Options
 
    def makeService(self, options):
        
        return internet.UNIXServer(options['socket'],
            server.Site(service.DockerService()))
 
serviceMaker = DockerServiceMaker()
