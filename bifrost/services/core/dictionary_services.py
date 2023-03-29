from bifrost.common.service import Service
from ait.core import cmd
from colorama import Fore
from ait.core import log
import traceback

class Command_Dictionary_Service(Service):
    def __init__(self):
        super().__init__()
        self.cmd_dict = cmd.getDefaultDict()
        self.start()

    async def reconfigure(self, topic, message, reply):
        await super().reconfigure(topic, message, reply)
        self.cmd_dict = cmd.getDefaultDict()
        return

    async def generate_command_object(self, topic, message, reply):
        # Don't actually use this, not langauge agnostic, we'll get rid of it someday.
        try:
            cmd_obj = self.cmd_dict.create(message)
            res = (cmd_obj.validate(), cmd_obj)
        except Exception as e:
            log.error(e)
            res = (False, None)
        await self.publish(reply, res)

    async def generate_command_raw(self, topic, message, reply):
        try:
            cmd_obj = self.cmd_dict.create(message)
            cmd_bytes = cmd_obj.encode()
            res = (cmd_obj.validate(), str(cmd_bytes))
        except Exception as e:
            log.error(e)
            log.error(traceback.print_exc())
            res = (False, None)
        await self.publish(reply, res)

    async def get_dictionary(self, topic, message, reply):
        # Don't actually use this, not langauge agnostic, we'll get rid of it someday.
        await self.publish(reply, self.cmd_dict)

    async def get_dictionary_json(self, topic, message, reply):
        await self.publish(reply, self.cmd_dict.toJSON())
