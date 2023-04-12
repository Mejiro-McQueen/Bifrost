from bifrost.common.service import Service
from bifrost.common.loud_exception import with_loud_coroutine_exception, with_loud_exception
import ast

class CLTU_Service(Service):

    @with_loud_exception
    def __init__(self):
        super().__init__()
        self.CLTU_start = bytearray(b'\xEB\x90')
        self.CLTU_tail = bytearray(b'\xC5\xC5\xC5\xC5\xC5\xC5\xC5\x79')
        self.start()

    @with_loud_coroutine_exception
    async def process(self, topic, cmd_struct, reply):
        cmd_struct.payload_bytes = self.CLTU_start + bytearray(cmd_struct.payload_bytes) + self.CLTU_tail
        await self.publish('Uplink.CmdMetaData.CLTU', cmd_struct)
        return cmd_struct

    @with_loud_coroutine_exception
    async def reconfigure(self, topic, message, reply):
        await super().reconfigure(topic, message, reply)
        self.CLTU_start = bytes.fromhex(self.CLTU_start[2:])
        self.CLTU_tail = bytes.fromhex(self.CLTU_tail[2:])
        return
