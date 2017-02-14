"""
Very limited reimplementation of some of `twisted.logger.Logger`'s public
API so we can use older Twisted versions that don't have the new logging
features.
"""

try:
    from twisted.logger import Logger
except ImportError:
    import logging
    from twisted.python import log

    class Logger(object):
        def debug(self, format, **kw):
            log.msg(format.format(**kw), logLevel=logging.DEBUG)

        def info(self, format, **kw):
            log.msg(format.format(**kw), logLevel=logging.INFO)

        def warn(self, format, **kw):
            log.msg(format.format(**kw), logLevel=logging.WARNING)

        def error(self, format, **kw):
            log.msg(format.format(**kw), logLevel=logging.ERROR)

        def critical(self, format, **kw):
            log.msg(format.format(**kw), logLevel=logging.CRITICAL)
