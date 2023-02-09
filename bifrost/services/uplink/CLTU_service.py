from bifrost.common.service import Service

class CLTU_Service(Service):

    def __init__(self):
        super().__init__()
        self.CLTU_start = bytearray(b'\xEB\x90')
        self.CLTU_tail = bytearray(b'\xC5\xC5\xC5\xC5\xC5\xC5\xC5\x79')
        self.start()

    async def process(self, topic, cmd_struct, reply):
        cmd_struct.payload_bytes = self.CLTU_start + bytearray(cmd_struct.payload_bytes) + self.CLTU_tail
        await self.publish('Uplink.CmdMetaData.CLTU', cmd_struct)
        return cmd_struct

    async def reconfigure(self, topic, message, reply):
        await super().reconfigure(topic, message, reply)
        return
