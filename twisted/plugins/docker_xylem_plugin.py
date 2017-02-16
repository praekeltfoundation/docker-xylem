import yaml

from zope.interface import implements

from twisted.python import filepath, usage
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
        sockfp = filepath.FilePath("/run/docker/plugins/xylem.sock")
        if not sockfp.parent().exists():
            sockfp.parent().makedirs()

        return internet.UNIXServer(
            config.get('socket', sockfp.path),
            server.Site(service.DockerService(config)))


serviceMaker = DockerServiceMaker()
