# Advanced Multi-Mission Operations System (AMMOS) Instrument Toolkit (AIT)
# Bespoke Link to Instruments and Small Satellites (BLISS)
#
# Copyright 2013, by the California Institute of Technology. ALL RIGHTS
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
AIT Commands

The ait.core.cmd module provides commands and command dictionaries.
Dictionaries contain command and argument definitions.
"""

import os
import pkg_resources
import struct
import yaml
from io import IOBase

import ait
from ait.core import json, util, log
import ast

MAX_CMD_WORDS = 54


class ArgDefn(json.SlotSerializer, object):
    """ArgDefn - Argument Definition

    Argument Definitions encapsulate all information required to define
    a single command argument.  This includes the argument name, its
    description, units, type, byte position within a command, name-value
    enumerations, and allowed value ranges.  Name, type, and byte
    position are required.  All others are optional.

    A fixed argument (fixed=True) defines a fixed bit pattern in that
    argument's byte position(s).
    """

    __slots__ = [
        "name",
        "desc",
        "units",
        "_type",
        "bytes",
        "_enum",
        "range",
        "fixed",
        "value",
    ]

    def __init__(self, *args, **kwargs):
        """Creates a new Argument Definition."""
        for slot in ArgDefn.__slots__:
            name = slot[1:] if slot.startswith("_") else slot
            setattr(self, name, kwargs.get(name, None))

    def __repr__(self):
        return util.toRepr(self)

    @property
    def enum(self):
        """The argument enumeration."""
        return self._enum

    @enum.setter
    def enum(self, value):
        self._enum = None
        if value is not None:
            self._enum = dict(reversed(pair) for pair in value.items())

    @property
    def nbytes(self):
        """The number of bytes required to encode this argument."""
        return self.type.nbytes

    @property
    def type(self):
        """The argument type."""
        return self._type

    @type.setter
    def type(self, value):
        from ait.core import dtype

        self._type = dtype.get(value) if type(value) is str else value

    @property
    def startword(self):
        """The argument start word in the command"""
        return self.slice().start / 2 + 1

    @property
    def startbit(self):
        """The argument start bit in the word"""
        return self.slice().start % 2 * 8

    def decode(self, bytes):
        """Decodes the given bytes according to this AIT Argument
        Definition.
        """
        value = self.type.decode(bytes)
        if self._enum is not None:
            for name, val in self._enum.items():
                if value == val:
                    value = name
                    break
        return value

    def encode(self, value):
        """Encodes the given value according to this AIT Argument
        Definition.
        """
        if not self.type:
            return bytearray()

        if type(value) == str and self.enum and value in self.enum:
            value = self.enum[value]
        res = self.type.encode(value)
        return res

    def slice(self, offset=0):
        """Returns a Python slice object (e.g. for array indexing) indicating
        the start and stop byte position of this Command argument.  The
        start and stop positions may be translated by the optional byte
        offset.
        """
        if type(self.bytes) is int:
            start = self.bytes
            stop = start + 1
        else:
            start = self.bytes[0]
            stop = self.bytes[1] + 1

        return slice(start + offset, stop + offset)

    def validate(self, value, messages=None):
        """Returns True if the given Argument value is valid, False otherwise.
        Validation error messages are appended to an optional messages
        array.
        """
        valid = True
        primitive = value
        if isinstance(value, str) and primitive[0] == '[' and primitive[-1] == ']':
            value = ast.literal_eval(value)
            primitive = value

        def log(msg):
            if messages is not None:
                messages.append(msg)

        if self.enum:
            if value not in self.enum.keys():
                valid = False
                args = (self.name, str(value))
                log("%s value '%s' not in allowed enumerated values." % args)
            else:
                primitive = int(self.enum[value])

        if self.type or isinstance(value, list):
            valid = self.type.validate(primitive, messages, self.name)

        if self.range:
            def check_prim_range(i):
                valid = True
                if i < self.range[0] or i > self.range[1]:
                    valid = False
                    args = (self.name, str(i), self.range[0], self.range[1])
                    log("%s value '%s' out of range [%d, %d]." % args)
                return valid

            if isinstance(value, list):
                valid = all([check_prim_range(i) for i in value])
            else:
                valid = check_prim_range(primitive)
        return valid


class Cmd(object):
    """Cmd - Command

    Commands reference their Command Definition and may contain arguments.
    """

    def __init__(self, defn, *args, **kwargs):
        """Creates a new AIT Command based on the given command
        definition and command arguments.  A Command may be created
        with either positional or keyword arguments, but not both.
        """
        self.defn = defn

        if len(args) > 0 and len(kwargs) > 0:
            msg = "A Cmd may be created with either positional or "
            msg += "keyword arguments, but not both."
            raise TypeError(msg)

        if len(kwargs) > 0:
            args = []
            for defn in self.defn.args:
                if defn.name in kwargs:
                    value = kwargs.pop(defn.name)
                else:
                    value = None
                args.append(value)

        self.args = args
        self._unrecognized = kwargs

    def __str__(self):
        #res = self.defn.name + " " + " ".join([str(a) for a in self.args])
        return repr(self)

    def __repr__(self):
        x = {k.name: v for (k, v) in self.arg_val_map().items()}
        res = self.defn.name + " -> args: " + str(x)
        return res

    def arg_val_map(self):
        """
        Map arg definiton to value
        """
        vals = {}
        index = 0
        for defn in self.defn.argdefns:
            if defn.fixed:
                vals[defn] = defn.value
            else:
                vals[defn] = self.args[index]
                index += 1
        return vals

    @property
    def desc(self):
        """The command description."""
        return self.defn.desc

    @property
    def name(self):
        """The command name."""
        return self.defn.name

    @property
    def opcode(self):
        """The command opcode."""
        return self.defn.opcode

    @property
    def subsystem(self):
        """The subsystem to which this command applies."""
        return self.defn.subsystem

    @property
    def argdefns(self):
        """The command argument definitions."""
        return self.defn.argdefns

    def encode(self):
        # TODO: Specify Opcode Size
        try:
            opcode = struct.pack(">H", self.defn.opcode)
        except struct.error:
            msg = f"The opcode: {hex(self.defn.opcode)} for command {self.name} "
            msg += "does not fit in an unsigned int. Check your Cmd Dictionary."
            raise ValueError(msg)

        encode = bytearray() + opcode
        index = 0
        x = []
        for defn in self.defn.argdefns:
            log.debug(defn)
            if defn.fixed:
                value = defn.value
            else:
                value = self.args[index]
                index += 1
            if value == 0 or value == '':
                encode += bytearray(defn._type.nbytes)
            else:
                encode += defn.encode(value)
        return encode

    def validate(self, messages=None):
        """Returns True if the given Command is valid, False otherwise.
        Validation error messages are appended to an optional messages
        array.
        """
        return self.defn.validate(self, messages)


class CmdDefn(json.SlotSerializer, object):
    """CmdDefn - Command Definition

    Command Definitions encapsulate all information required to define a
    single command.  This includes the command name, its opcode,
    subsystem, description and a list of argument definitions.  Name and
    opcode are required.  All others are optional.
    """

    __slots__ = ("name", "_opcode", "subsystem", "ccsds", "title", "desc", "argdefns")

    def __init__(self, *args, **kwargs):
        """Creates a new Command Definition."""
        for slot in CmdDefn.__slots__:
            name = slot[1:] if slot.startswith("_") else slot
            setattr(self, slot, kwargs.get(name, None))

        if self.ccsds:
            import ait.core.ccsds as ccsds

            self.ccsds = ccsds.CcsdsDefinition(**self.ccsds)

        if self.argdefns is None:
            self.argdefns = []

    def __repr__(self):
        return util.toRepr(self)

    @property
    def args(self):
        """The argument definitions to this command (excludes fixed
        arguments).
        """
        return filter(lambda a: not a.fixed, self.argdefns)

    @property
    def nargs(self):
        """The number of arguments to this command (excludes fixed
        arguments).
        """
        return len(list(self.args))

    @property
    def nbytes(self):
        """The number of bytes required to encode this command.

        Encoded commands are comprised of a two byte opcode, followed by a
        one byte size, and then the command argument bytes.  The size
        indicates the number of bytes required to represent command
        arguments.
        """
        return len(self.opcode) + 1 + sum(arg.nbytes for arg in self.argdefns)

    @property
    def opcode(self):
        """Returns the opcode for the given command."""
        return self._opcode

    @property
    def argsize(self):
        """The total size in bytes of all the command arguments."""
        argsize = sum(arg.nbytes for arg in self.argdefns)
        return argsize if len(self.argdefns) > 0 else 0

    def staging_required(self):
        maxbytes = getMaxCmdSize()
        if self.argsize > maxbytes:
            msg = "Command %s larger than %d bytes. Staging required."
            log.debug(msg, self.name, maxbytes)
            return False
        else:
            return True

    def toJSON(self):  # noqa
        obj = super(CmdDefn, self).toJSON()
        obj["arguments"] = obj.pop("argdefns")

        if self.ccsds is None:
            obj.pop("ccsds", None)

        return obj

    def validate(self, cmd, messages=None):
        """Returns True if the given Command is valid, False otherwise.
        Validation error messages are appended to an optional messages
        array.
        """
        valid = True
        args = [arg for arg in cmd.args if arg is not None]

        if self.nargs != len(args):
            valid = False
            if messages is not None:
                msg = "Expected %d arguments, but received %d."
                messages.append(msg % (self.nargs, len(args)))

        for defn, value in zip(self.args, cmd.args):
            if value is None:
                valid = False
                if messages is not None:
                    messages.append('Argument "%s" is missing.' % defn.name)
            elif defn.validate(value, messages) is False:
                valid = False

        if len(cmd._unrecognized) > 0:
            valid = False
            if messages is not None:
                for name in cmd.unrecognized:
                    messages.append('Argument "%s" is unrecognized.' % name)

        return valid


class CmdDict(dict): # Daily reminder that this only runs if the pkl does not exist
    """CmdDict

    Command Dictionaries provide a Python dictionary (i.e. hashtable)
    interface mapping Command names to Command Definitions.
    """

    def __init__(self, *args, **kwargs):
        """Creates a new Command Dictionary from the given command dictionary
        filename.
        """
        self.filename = None
        self.opcodes = {}

        if len(args) == 1 and len(kwargs) == 0 and type(args[0]) == str:
            dict.__init__(self)
            self.load(args[0])
        else:
            dict.__init__(self, *args, **kwargs)
            
    def add(self, defn):
        """Adds the given Command Definition to this Command Dictionary."""
        if defn.name not in self:
            self[defn.name] = defn
        else:
            msg = "Duplicate Command name '%s'" % defn.name
            log.error(msg)
            raise util.YAMLError(msg)

        if defn._opcode not in self.opcodes or True:  # Work around for shared opcodes (e.g. NASA cFS)
            self.opcodes[defn._opcode] = defn
        else:
            msg = "Duplicate Command opcode '%s'" % defn._opcode
            log.error(msg)
            raise util.YAMLError(msg)

    def create(self, name, *args, **kwargs):
        """Creates a new AIT command with the given arguments."""
        # Gets called on validate, for high IQ reasons.
        tokens = name.split()
        if len(tokens) > 1 and (args or kwargs):
            msg = "A Cmd may be created with either positional arguments "
            msg += "(passed as a string or a Python list) or keyword "
            msg += "arguments, but not both."
            raise TypeError(msg)

        if len(tokens) > 1:
            # Tokens = args if not args but also name, but not if kwargs or args.
            # This is what I call a low IQ move
            args = []
            name = tokens[0]
            for t in tokens[1:]:
                if isinstance(t, str) and t[0] == '[' and t[-1] == ']':
                    args.append(ast.literal_eval(t))
                else:
                    args.append(util.toNumber(t, t))

        defn = self.get(name, None)

        if defn is None:
            raise TypeError("Unrecognized command: %s" % name)

        r = createCmd(defn, *args, **kwargs)
        return r

    def decode(self, bytes): # Guaranteed not to work due to shared opcodes
        """Decodes the given bytes according to this AIT Command
        Definition.
        """
        opcode = struct.unpack(">H", bytes[0:2])[0]
        name = None
        args = []

        if opcode in self.opcodes:
            defn = self.opcodes[opcode]
            name = defn.name
            stop = 3

            for arg in defn.argdefns:
                start = stop
                stop = start + arg.nbytes
                if arg.fixed:
                    pass  # FIXME: Confirm fixed bytes are as expected?
                else:
                    args.append(arg.decode(bytes[start:stop]))

        return self.create(name, *args)

    def load(self, content):
        """Loads Command Definitions from the given YAML content into
        into this Command Dictionary.  Content may be either a
        filename containing YAML content or a YAML string.

        Load has no effect if this Command Dictionary was already
        instantiated with a filename or YAML content.
        """
        if self.filename is None:
            if os.path.isfile(content):
                self.filename = content
                stream = open(self.filename, "rb")
            else:
                stream = content

            cmds = yaml.load(stream, Loader=yaml.Loader)
            cmds = handle_includes(cmds)
            for cmd in cmds:
                self.add(cmd)

            if isinstance(stream, IOBase):
                stream.close()

    def toJSON(self):  # noqa
        return {name: defn.toJSON() for name, defn in self.items()}


def getDefaultCmdDict(reload=False):  # noqa
    return getDefaultDict(reload=reload)


def getDefaultDict(reload=False):  # noqa
    create_cmd_dict_func = globals().get('createCmdDict', None)
    loader = create_cmd_dict_func if create_cmd_dict_func else CmdDict
    return util.getDefaultDict(__name__, "cmddict", loader, reload)


def getDefaultDictFilename():  # noqa
    return ait.config.cmddict.filename


def getDefaultSchema():  # noqa
    return pkg_resources.resource_filename("ait.core", "data/cmd_schema.json")


def getMaxCmdSize():  # noqa
    """Returns the maximum size TReK command in bytes

    Converts from words to bytes (hence the ``* 2``) and
    removes 1 word for CCSDS header (-1)
    """
    return (MAX_CMD_WORDS - 1) * 2


def handle_includes(defns):
    """Recursive handling of includes for any input list of defns.
    The assumption here is that when an include is handled by the
    pyyaml reader, it adds them as a list, which is stands apart from the rest
    of the expected YAML definitions.
    """
    newdefns = []
    for d in defns:
        if isinstance(d, list):
            newdefns.extend(handle_includes(d))
        else:
            newdefns.append(d)

    return newdefns


def YAMLCtor_ArgDefn(loader, node):  # noqa
    fields = loader.construct_mapping(node, deep=True)
    fields["fixed"] = node.tag == "!Fixed"
    return createArgDefn(**fields)  # noqa


def YAMLCtor_CmdDefn(loader, node):  # noqa
    fields = loader.construct_mapping(node, deep=True)
    fields["argdefns"] = fields.pop("arguments", None)
    return createCmdDefn(**fields)  # noqa


def YAMLCtor_include(loader, node):  # noqa
    # Get the path out of the yaml file
    name = os.path.join(os.path.dirname(loader.name), node.value)
    data = None
    with open(name, "r") as f:
        data = yaml.load(f, Loader=yaml.Loader)
    return data


yaml.add_constructor("!include", YAMLCtor_include)
yaml.add_constructor("!Command", YAMLCtor_CmdDefn)
yaml.add_constructor("!Argument", YAMLCtor_ArgDefn)
yaml.add_constructor("!Fixed", YAMLCtor_ArgDefn)

util.__init_extensions__(__name__, globals())
