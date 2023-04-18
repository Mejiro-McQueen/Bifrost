from bifrost.common.service import Service
from bifrost.common.loud_exception import with_loud_coroutine_exception, with_loud_exception
from bifrost.services.core.commanding.cmd_meta_data import CmdMetaData
from ait.core import log


class NASA_FSS_Service(Service):
    """
    This service is intended to be a work around for various quirks of the current state of the ITC Parser:
    1. FSS Commands are: CLTU(BCH(TCTF(CMD)))
    2. CFS Commands are: CLTU(BCH(TCTF(SPACE_PACKET(CMD))))

    Thus this service bypasses CCSDS packetization while providing a mechanism for controlling the FSS_Command
    through scripts.

    Another quirk of the ITC Parser:
    You need to:
    1. Send the command.
    2. Sleep or watch the command return from TCP_Service
    3. Disconnect and reconnect the connection to the ITC Parser Uplink
    """
    
    @with_loud_exception
    def __init__(self):
        super().__init__()
        self.start()

    @with_loud_coroutine_exception
    async def directive_command(self, topic, data, reply):
        cmd_struct = await self.request('Bifrost.Services.Dictionary.Command.Generate', data)

        if cmd_struct.valid:
            await self.publish('Uplink.CmdMetaData.FSS_Command', cmd_struct)
            response = f'OK, {data}'
        else:
            response = f'Error, {data}'
        await self.publish(reply, response)
        log.info(response)

    @with_loud_coroutine_exception
    async def reconfigure(self, topic, message, reply):
        await super().reconfigure(topic, message, reply)
        return
