from bifrost.common.service import Service
from bifrost.common.loud_exception import with_loud_coroutine_exception, with_loud_exception
from bifrost.services.core.commanding.cmd_meta_data import CmdMetaData
from ait.core import log


class NASA_FSS_Service(Service):
    @with_loud_exception
    def __init__(self):
        super().__init__()
        self.start()

    @with_loud_coroutine_exception
    async def directive_command(self, topic, data, reply):
        res = await self.request('Bifrost.Services.Dictionary.Command.Raw', data)
        valid, cmd_bytes = res

        if valid:
            pl = CmdMetaData(data, cmd_bytes)
            await self.publish('Uplink.CmdMetaData.FSS_Command', pl)
            response = f'OK, {data}'
        else:
            response = f'Error, {data}'
        await self.publish(reply, response)
        log.info(response)

    @with_loud_coroutine_exception
    async def reconfigure(self, topic, message, reply):
        await super().reconfigure(topic, message, reply)
        return
