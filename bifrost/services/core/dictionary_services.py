from bifrost.common.service import Service
from bifrost.common.loud_exception import with_loud_coroutine_exception, with_loud_exception
from bifrost.services.core.commanding.cmd_meta_data import CmdMetaData
from ait.core import cmd, tlm
from colorama import Fore
from ait.core import log
import traceback
from bifrost.services.core.commanding.command_loader_service import command_type_hueristic, Command_Type

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
    async def generate_command(self, topic, message, reply):
        # TODO: AIT Enforces: Unique CMD Opcodes, Opcodes must fit in uint. That's none of their business.
        try:
            cmd_obj = self.cmd_dict.create(message)
            cmd_bytes = cmd_obj.encode()
            apid = str(hex(cmd_obj.opcode))
            res = (cmd_obj.validate(), cmd_bytes)
            res = CmdMetaData(message, cmd_bytes, apid, cmd_obj.validate())
        except Exception as e:
            log.error(e)
            log.error(traceback.print_exc())
            res = CmdMetaData(message, bytes(''))
        if reply:
            await self.publish(reply, res)
        return res

    @with_loud_coroutine_exception
    async def get_dictionary_json(self, topic, message, reply):
        await self.publish(reply, self.cmd_dict.toJSON())


