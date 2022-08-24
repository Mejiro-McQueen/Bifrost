# Advanced Multi-Mission Operations System (AMMOS) Instrument Toolkit (AIT)
# Bespoke Link to Instruments and Small Satellites (BLISS)
#
# Copyright 2008, by the California Institute of Technology. ALL RIGHTS
# RESERVED. United States Government Sponsorship acknowledged. Any
# commercial use must be negotiated with the Office of Technology Transfer
# at the California Institute of Technology.
#
# This software may be subject to U.S. export control laws. By accepting
# this software, the user agrees to comply with all applicable U.S. export
# laws and regulations. User has the responsibility to obtain export licenses,
# or other export authority as may be required before exporting such
# information to foreign countries or providing access to foreign persons.

"""
AIT Logging

The ait.core.log module logs warnings, errors, and other information to
standard output and via syslog.
"""

import sys
import socket
import datetime
import time

import logging
import logging.handlers

import ait
import ait.core
from ait.core.sdls_utils import SDLS_Type, get_sdls_type

NOTICE = logging.INFO + 1
COMMAND = logging.INFO + 2
PROGRAM = logging.INFO + 3
logging.addLevelName(NOTICE, "NOTICE")
logging.addLevelName(COMMAND, "COMMAND")
logging.addLevelName(PROGRAM, "PROGRAM")


class LogFormatter(logging.Formatter):
    """LogFormatter

    Log output format is:

        YYYY-MM-DDTHH:MM:SS | levelname | message

    Where levelname is one of 'critical', 'error', 'warning', 'command',
    'info', or 'debug'.
    """

    DATEFMT = "%Y-%m-%dT%H:%M:%S"

    def __init__(self):
        """LogFormatter()

        Creates and returns a new LogFormatter.
        """
        format = "%(asctime)s | %(levelname)-8s | %(module)s -> %(funcName)s => %(message)s"
        datefmt = self.DATEFMT
        logging.Formatter.__init__(self, format, datefmt)

    def formatTime(self, record, datefmt=None):  # noqa
        """Return the creation time of the specified LogRecord as formatted
        text."""
        if datefmt is None:
            datefmt = "%Y-%m-%d %H:%M:%S"

        ct = self.converter(record.created)
        t = time.strftime(datefmt, ct)
        s = "%s.%03d" % (t, record.msecs)

        return s


class SysLogFormatter(logging.Formatter):
    """SysLogFormatter"""

    BSD_FMT = "%(asctime)s %(hostname)s %(name)s[%(process)d]: %(message)s"
    BSD_DATEFMT = "%b %d %H:%M:%S"

    SYS_DATEFMT = "%Y-%m-%dT%H:%M:%S.%fZ"
    SYSLOG_FMT = (
        "1 %(asctime)s %(hostname)s %(name)s %(process)d " "%(levelname)s - %(message)s"
    )

    def __init__(self, bsd=False):
        """LogFormatter([bsd=False])

        Creates and returns a new SysLogFormatter.  If BSD is True, the
        sylog message is formatted according to the BSD Syslog Protocol:

            RFC 3164 - The BSD Syslog Protocol
            http://tools.ietf.org/html/rfc3164

        Otherwise, the syslog message is formatted according to the Syslog
        Protocol:

            RFC 5424 - The Syslog Protocol
            http://tools.ietf.org/html/rfc5424
        """
        self.bsd = bsd
        self.hostname = socket.gethostname()

        if self.bsd is True:
            format = self.BSD_FMT
        else:
            format = self.SYSLOG_FMT

        logging.Formatter.__init__(self, format)

    def format(self, record):
        """Returns the given LogRecord as formatted text."""
        record.hostname = self.hostname
        return logging.Formatter.format(self, record)

    def formatTime(self, record, datefmt=None):  # noqa
        """Returns the creation time of the given LogRecord as formatted text.

        NOTE: The datefmt parameter and self.converter (the time
        conversion method) are ignored.  BSD Syslog Protocol messages
        always use local time, and by our convention, Syslog Protocol
        messages use UTC.
        """
        if self.bsd:
            lt_ts = datetime.datetime.fromtimestamp(record.created)
            ts = lt_ts.strftime(self.BSD_DATEFMT)
            if ts[4] == "0":
                ts = ts[0:4] + " " + ts[5:]
        else:
            utc_ts = datetime.datetime.utcfromtimestamp(record.created)
            ts = utc_ts.strftime(self.SYS_DATEFMT)
        return ts


class SysLogHandler(logging.handlers.SysLogHandler):
    def __init__(self, address=None, facility=None, socktype=None):
        self.bsd = False

        if address is None:
            if sys.platform == "darwin":
                address = "/var/run/syslog"
                self.bsd = True
            else:
                address = ("localhost", logging.handlers.SYSLOG_UDP_PORT)

        if facility is None:
            facility = logging.handlers.SysLogHandler.LOG_USER

        logging.handlers.SysLogHandler.__init__(self, address, facility, socktype)

        self.priority_map["NOTICE"] = "notice"
        self.priority_map["COMMAND"] = "notice"
        self.priority_map["PROGRAM"] = "notice"

        self.setFormatter(SysLogFormatter(self.bsd))


def add_local_handlers(logger):
    """Adds logging handlers to logger to log to the following local
    resources:

        1.  The terminal
        2.  localhost:514  (i.e. syslogd)
        3.  localhost:2514 (i.e. the AIT GUI syslog-like handler)
    """
    termlog = logging.StreamHandler()
    termlog.setFormatter(LogFormatter())

    logger.addHandler(termlog)
    logger.addHandler(SysLogHandler())
    logger.addHandler(SysLogHandler(("localhost", 2514)))


def add_remote_handlers(logger):
    """Adds logging handlers to logger to remotely log to:

        ait.config.logging.hostname:514  (i.e. syslogd)

    If not set or hostname cannot be resolved, this method has no
    effect.
    """
    try:
        hostname = ait.config.logging.hostname

        # Do not "remote" log to this host, as that's already covered
        # by addLocalHandlers().
        if socket.getfqdn() != hostname:
            socket.getaddrinfo(hostname, None)
            logger.addHandler(SysLogHandler((hostname, 514)))

    except AttributeError:
        pass  # No ait.config.logging.hostname

    except socket.gaierror:
        pass  # hostname cannot be resolved (e.g. no Internet)


def init():
    global logger, crit, debug, error, info, warn

    try:
        name = ait.config.logging.name
    except AttributeError:
        name = "ait"

    if logging.getLogger(name) == logger:
        for h in logger.handlers[:]:
            logger.removeHandler(h)

    logger = logging.getLogger(name)
    crit = logger.critical
    debug = logger.debug
    error = logger.error
    info = logger.info
    warn = logger.warning

    logger.setLevel(logging.INFO)

    logger.addFilter(SecurityFilter())
    logger.addFilter(AnnoyingFilter())
    add_local_handlers(logger)
    add_remote_handlers(logger)


reinit = init


def parse_syslog(msg):
    """Parses Syslog messages (RFC 5424)

    The `Syslog Message Format (RFC 5424)
    <https://tools.ietf.org/html/rfc5424#section-6>`_ can be parsed with
    simple whitespace tokenization::

        SYSLOG-MSG = HEADER SP STRUCTURED-DATA [SP MSG]
        HEADER     = PRI VERSION SP TIMESTAMP SP HOSTNAME
                     SP APP-NAME SP PROCID SP MSGID
        ...
        NILVALUE   = "-"

    This method does not return STRUCTURED-DATA.  It parses NILVALUE
    ("-") STRUCTURED-DATA or simple STRUCTURED-DATA which does not
    contain (escaped) ']'.

    :returns: A dictionary keyed by the constituent parts of the
    Syslog message.
    """
    tokens = msg.split(" ", 6)
    result = {}

    if len(tokens) > 0:
        pri = tokens[0]
        start = pri.find("<")
        stop = pri.find(">")

        if start != -1 and stop != -1:
            result["pri"] = pri[start + 1 : stop]
        else:
            result["pri"] = ""

        if stop != -1 and len(pri) > stop:
            result["version"] = pri[stop + 1 :]
        else:
            result["version"] = ""

    result["timestamp"] = tokens[1] if len(tokens) > 1 else ""
    result["hostname"] = tokens[2] if len(tokens) > 2 else ""
    result["appname"] = tokens[3] if len(tokens) > 3 else ""
    result["procid"] = tokens[4] if len(tokens) > 4 else ""
    result["msgid"] = tokens[5] if len(tokens) > 5 else ""
    result["msg"] = ""

    if len(tokens) > 6:
        # The following will work for NILVALUE STRUCTURED-DATA or
        # simple STRUCTURED-DATA which does not contain ']'.
        rest = tokens[6]
        start = rest.find("-")

        if start == -1:
            start = rest.find("]")

        if len(rest) > start:
            result["msg"] = rest[start + 1 :].strip()

    return result


def begin():
    """Command-line tools should begin logging with core.log.begin() to
    log the command name and arguments.
    """
    logger.log(PROGRAM, " ".join(sys.argv))


def end():
    """Command-line tools should end logging with log.end() to log the
    completion of the command.
    """
    logger.log(PROGRAM, "done.")
    logging.shutdown()


def command(*args, **kwargs):
    logger.log(COMMAND, *args, **kwargs)


def program(*args, **kwargs):
    logger.log(PROGRAM, *args, **kwargs)


def notice(*args, **kwargs):
    logger.log(NOTICE, *args, **kwargs)


class SecurityFilter(logging.Filter):
    def filter(self, record):
        sdls_type = get_sdls_type()
        black_list_modules = []
        if sdls_type is SDLS_Type.ENC or sdls_type is SDLS_Type.AUTH:
            black_list_modules = ['TCTF_Manager',
                                  'tctf',
                                  'PacketPadder',
                                  'PacketAccumulator',
                                  ]

        elif sdls_type is SDLS_Type.CLEAR or sdls_type is sdls_type.FINAL:
            black_list_modules = ["EncrypterPlugin",
                                  "encrypter",
                                  "kmc_encrypter",
                                  ]

        if record.module in black_list_modules:
            logger.info(f"SDLS_Type is {sdls_type}: Log messages for {record.module} are blacklisted.")
            return False
        else:
            return True

class AnnoyingFilter(logging.Filter):
    black_list_phrases = ["specifies nonexistent path",
                          "No handlers specified for",
                          "Added outbound stream",
                          "No plugin outputs specified for",
                          "Starting <Plugin name=",
                          "Subscribing <Plugin name=",
                          "Added plugin <Plugin name=",
                          "Added inbound stream",
                          "Starting <ZMQStream name=",
                          "Subscribing <ZMQStream name=",
                          "Starting",
                          "Current pickle file loaded:",
                          "Published message from",
                          "received message from",
                          "to allow ZeroQM connection to complete",
                          "Added config for deferred plugin",
                          "Spawning <PluginsProcess",
                          "No plugin inputs specified",
                          "No streams available for telemetry API",
                          
                          ]
    black_list_modules = ["dmc"]
    def filter(self, record):
        msg = record.getMessage()
        res = [phrase in msg for phrase in self.black_list_phrases]
        if any(res):
            return False
        elif record.module in self.black_list_modules:
            return False
        else:
            return True
        
# These are "guaranteed" at runtime to be not-None. Marking this as
# type `Any` addresses mypy issues where log calls are marked as
# "None" being not callable.
logger = None
crit = None
debug = None
error = None
info = None
warn = None

init()
