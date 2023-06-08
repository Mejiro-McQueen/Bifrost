from bitarray import bitarray
import ait.core
from ait.core import log
from bifrost.common.service import Service


class CCSDS_Randomizer_Service(Service):

    def __init__(self):
        super().__init__()
        ccsds_random_sequence = bitarray('111111110100100000001110110000001001101000001101011100001011110010\
            001110001011001001001110101101101001111011011101000110110011100101101010010111011111011100110000\
                110010101000101011111100111110000010100001000011110001100010001001010011001101111010101011000') #255 bits generated using a LFSR
        self.random_sequence = ccsds_random_sequence * 32 + ccsds_random_sequence[0:32] #1024 bytes worth of random bits from the LFSR
        self.start()

    def process(self, cmd_struct):
        if len(cmd_struct.payload_bytes) != 1024:
            log.error(f"found TCTF with size {len(cmd_struct.payload_bytes)}. Doing nothing.")
            return
        input_data_bit_array = bitarray()
        input_data_bit_array.frombytes(bytes(cmd_struct.payload_bytes))
        randomized_frame_bitarray = input_data_bit_array ^ self.random_sequence
        randomized_frame = bytearray(randomized_frame_bitarray.tobytes())
        cmd_struct.payload_bytes = randomized_frame
        ait.core.log.debug(f"Added randomization. Randomized frame: {randomized_frame}")
        return cmd_struct

    async def randomize_sdls(self, topic, cmd_struct, reply):
        cmd_struct = self.process(cmd_struct)
        await self.stream('Uplink.CmdMetaData.SDLS.Random', cmd_struct)

    async def randomize_tctf(self, topic, cmd_struct, reply):
        cmd_struct = self.process(cmd_struct)
        await self.stream('Uplink.CmdMetaData.TCTF.Random', cmd_struct)

    async def reconfigure(self, topic, message, reply):
        await super().reconfigure(topic, message, reply)
        return
