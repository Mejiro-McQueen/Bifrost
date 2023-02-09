from bifrost.common.service import Service
from ait.core import log
from bifrost.services.uplink.tctf_service import check_data_field_size, get_max_data_field_size
from bifrost.common.loud_exception import with_loud_coroutine_exception, with_loud_exception


class Packet_Padder(Service):
    @with_loud_exception
    def __init__(self):
        super().__init__()
        self.size_pad_octets = get_max_data_field_size()
        self.start()

    @with_loud_coroutine_exception
    async def process(self, topic, cmd_struct, reply):
        if not cmd_struct:
            log.error(f"received no data from {topic}.")
        if not check_data_field_size(cmd_struct.payload_bytes):
            log.error(f"initial data from {topic} is oversized.")
            cmd_struct.payload_size_valid = False
        if len(cmd_struct.payload_bytes) < self.size_pad_octets:
            fill = bytearray(self.size_pad_octets - len(cmd_struct.payload_bytes))
            cmd_struct.payload_bytes += fill
        if not check_data_field_size(cmd_struct.payload_bytes):
            log.error("Created oversized payload.")
            cmd_struct.payload_size_valid = False
        log.debug(f"publishing payload of size: {len(cmd_struct.payload_bytes)}")
        #cmd_struct.processors.append(self.__class__)
        await self.publish('Uplink.CmdMetaData.Padded', cmd_struct)

    @with_loud_coroutine_exception
    async def reconfigure(self, topic, message, reply):
        await super().reconfigure(topic, message, reply)
        return
