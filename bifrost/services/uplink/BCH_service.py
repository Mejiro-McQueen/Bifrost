from bifrost.common.service import Service
from ait.core import log
from bifrost.common.loud_exception import with_loud_coroutine_exception, with_loud_exception
from ait.dsn.bch import BCH
import math

class BCH_Service(Service):
    @with_loud_exception
    def __init__(self):
        super().__init__()
        self.start()

    @with_loud_coroutine_exception
    async def encode_cmd_metadata(self, topic, cmd_metadata, reply):
        cmd_metadata.payload_bytes = self.process(cmd_metadata.payload_bytes)
        await self.publish('Uplink.CmdMetaData.TCTF.BCH', cmd_metadata)

    @with_loud_coroutine_exception
    async def encode(self, topic, data, reply):
        if not data:
            data = ''
        else:
            data = self.process(data)
        await self.publish(reply, data)

    @with_loud_coroutine_exception
    async def reconfigure(self, topic, message, reply):
        await super().reconfigure(topic, message, reply)
        return

    def process(self, input_data, topic=None):
        number_of_chunks = math.floor(len(input_data)/7)
        remainder_bytes = len(input_data) % 7
        output_bytes = bytearray()

        for chunk_number in range(number_of_chunks):
            beginning_index = chunk_number*7
            chunk = input_data[beginning_index:beginning_index+7]
            chunk_with_bch = BCH.generateBCH(chunk)
            output_bytes = output_bytes + chunk_with_bch

        # handle case where number of bytes is not evenly divisible by 7
        # CCSDS standard states add alternating 0/1 fill bits starting with 0
        if remainder_bytes != 0:
            number_of_filler_bytes = 7 - remainder_bytes
            filler_bytes = bytearray(b"\x55")*number_of_filler_bytes
            last_chunk = input_data[-remainder_bytes:] + filler_bytes
            last_chunk_with_bch = BCH.generateBCH(last_chunk)
            output_bytes = output_bytes + last_chunk_with_bch

        return output_bytes
