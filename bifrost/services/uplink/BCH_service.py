from bifrost.common.service import Service
from ait.core import log
from bifrost.common.loud_exception import with_loud_coroutine_exception, with_loud_exception
from ait.dsn.bch import BCH


class BCH_Service(Service):
    @with_loud_exception
    def __init__(self):
        super().__init__()
        self.start()

    @with_loud_coroutine_exception
    async def encode_cmd_metadata(self, topic, cmd_metadata, reply):
        cmd_metadata.payload_bytes = BCH.generateBCH(cmd_metadata.payload_bytes)
        await self.publish('Uplink.CmdMetaData.TCTF.BCH', cmd_metadata)

    @with_loud_coroutine_exception
    async def encode(self, topic, data, reply):
        if not data:
            data = ''
        else:
            data = BCH.generateBCH(data)
        await self.publish(reply, data)

    @with_loud_coroutine_exception
    async def reconfigure(self, topic, message, reply):
        await super().reconfigure(topic, message, reply)
        return
