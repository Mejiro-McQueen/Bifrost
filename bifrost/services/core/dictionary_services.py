from bifrost.common.service import Service
from bifrost.common.loud_exception import with_loud_coroutine_exception, with_loud_exception
from ait.core import cmd, tlm
from colorama import Fore
from ait.core import log
import traceback


class Command_Dictionary_Service(Service):
    @with_loud_exception
    def __init__(self):
        super().__init__()
        self.cmd_dict = cmd.getDefaultDict()
        self.start()

    @with_loud_coroutine_exception
    async def reconfigure(self, topic, message, reply):
        if message:
            await super().reconfigure(topic, message, reply)
        self.cmd_dict = cmd.getDefaultDict(True)
        self.tlm_dict = tlm.getDefaultDict(True) # Purely for reload side effect
        log.info("Dictionaries reloaded!")
        return

    @with_loud_coroutine_exception
    async def generate_command_object(self, topic, message, reply):
        # Don't actually use this, not langauge agnostic, we'll get rid of it someday.
        try:
            cmd_obj = self.cmd_dict.create(message)
            res = (cmd_obj.validate(), cmd_obj)
        except Exception as e:
            log.error(e)
            res = (False, None)
        await self.publish(reply, res)

    @with_loud_coroutine_exception
    async def generate_command_raw(self, topic, message, reply):
        # TODO: AIT Enforces: Unique CMD Opcodes, Opcodes must fit in uint. That's none of their business.
        try:
            cmd_obj = self.cmd_dict.create(message)
            cmd_bytes = cmd_obj.encode()
            res = (cmd_obj.validate(), cmd_bytes)
        except Exception as e:
            log.error(e)
            log.error(traceback.print_exc())
            res = (False, None)
        await self.publish(reply, res)

    @with_loud_coroutine_exception
    async def get_dictionary(self, topic, message, reply):
        # Don't actually use this, not langauge agnostic, we'll get rid of it someday.
        await self.publish(reply, self.cmd_dict)

    @with_loud_coroutine_exception
    async def get_dictionary_json(self, topic, message, reply):
        await self.publish(reply, self.cmd_dict.toJSON())
