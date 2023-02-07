import ait.core
from ait.core.server import Plugin
from ait.core import log
from ait.dsn.sle.frames import AOSTransFrame
from binascii import crc_hqx
from dataclasses import dataclass
import ait
from ait.core.message_types import MessageType as MT
from colorama import Fore
import asyncio


@dataclass
class TaggedFrame:
    frame: bytearray
    vcid: int
    channel_counter: int = 0
    absolute_counter: int = 0
    corrupt_frame: bool = False
    out_of_sequence: bool = False
    idle: bool = False

    def get_map(self):
        res = {'channel_counter': self.channel_counter,
               'absolute_counter': self.absolute_counter,
               'vcid': self.vcid,
               'corrupt_frame': self.corrupt_frame,
               'out_of_sequence': self.out_of_sequence,
               'is_idle': self.idle,
               'frame': self.frame.hex()}
        return res


class AOS_Tagger():
    crc_func = crc_hqx
    frame_counter_modulo = 16777216  # As defined in CCSDS ICD: https://public.ccsds.org/Pubs/732x0b4.pdf

    def __init__(self, publisher):
        self.publish = publisher
        self.absolute_counter = 0
        vcids = ait.config.get('dsn.sle.aos.virtual_channels')._config  # what a low IQ move...
        vcids['Unknown'] = None
        self.vcid_sequence_counter = {i: 0 for i in vcids.keys()}
        self.vcid_loss_count = {**self.vcid_sequence_counter}
        self.vcid_corrupt_count = {**self.vcid_sequence_counter}
        self.hot = {i: False for i in self.vcid_sequence_counter.keys()}
        return

    def subset_map(self):
        m = {'absolute_counter': self.absolute_counter,
             'vcid_counter': self.vcid_sequence_counter,
             'vcid_losses': self.vcid_loss_count,
             'vcid_corruptions': self.vcid_corrupt_count}
        return m

    async def tag_frame(self, raw_frame):

        async def tag_corrupt():
            try:
                data_field_end_index = frame.defaultConfig.data_field_endIndex
            except Exception as e:
                log.error(f"Could not decode AOS Frame!: {e}")
                log.error(f"Assuming frame is corrupted.")
                return True

            expected_ecf = raw_frame[-2:]
            block = raw_frame[:data_field_end_index]
            actual_ecf = self.crc_func(block, 0xFFFF).to_bytes(2, 'big')
            tagged_frame.corrupt_frame = actual_ecf != expected_ecf

            if tagged_frame.corrupt_frame:
                log.error(f"Expected ECF {expected_ecf} did not match actual ecf {actual_ecf}.")
                if tagged_frame.vcid not in self.vcid_corrupt_count:
                    tagged_frame.vcid = "Unknown"
                self.vcid_corrupt_count[tagged_frame.vcid] += 1
                #await self.publish("Bifrost.Errors.Frames.ECF_Mismatch", self.vcid_corrupt_count)
            return

        async def tag_out_of_sequence():
            if tagged_frame.vcid not in self.vcid_sequence_counter or tagged_frame.vcid == 'Unknown':
                # Junk Frame
                tagged_frame.out_of_sequence = True
                tagged_frame.absolute_counter += 1
                return 
            expected_vcid_count = (self.vcid_sequence_counter[tagged_frame.vcid] % self.frame_counter_modulo) + 1

            #rint(f"{tagged_frame.vcid=} {expected_vcid_count=} {tagged_frame.channel_counter=} {self.hot[tagged_frame.vcid]=}")
            #print(self.hot[tagged_frame.vcid] and not tagged_frame.idle and not tagged_frame.channel_counter == expected_vcid_count)

            if self.hot[tagged_frame.vcid] and not tagged_frame.idle and not tagged_frame.channel_counter == expected_vcid_count:
                tagged_frame.out_of_sequence = True
                log.warn(f"Out of Sequence Frame VCID {tagged_frame.vcid}: expected {expected_vcid_count} but got {tagged_frame.channel_counter}")
                self.vcid_loss_count[tagged_frame.vcid] += 1
                #await self.publish("Bifrost.Errors.Frames.Out_Of_Sequence", self.vcid_loss_count)

            self.hot[tagged_frame.vcid] = True
            self.vcid_sequence_counter[tagged_frame.vcid] = tagged_frame.channel_counter
            self.absolute_counter += 1
            tagged_frame.absolute_counter = self.absolute_counter
            return

        frame = AOSTransFrame(raw_frame)
        vcid = int(frame.virtual_channel)
        idle = frame.is_idle_frame
        channel_counter = int.from_bytes(frame.get('virtual_channel_frame_count'), 'big')
        tagged_frame = TaggedFrame(frame=raw_frame,
                                   vcid=vcid,
                                   idle=idle,
                                   channel_counter=channel_counter)

        await tag_corrupt()
        await tag_out_of_sequence()

        return tagged_frame


class AOS_FEC_Check_Plugin(Plugin):
    '''
    Check if a AOS frame fails a Forward Error Correction Check

    PROTIP: Do add more than 1 callback per queue here
    '''
    def __init__(self):
        self.tagger = AOS_Tagger(self.publish)
        super().__init__()
        self.report_time = 5
        self.loop.create_task(self.supervisor_tree())
        self.start()
        
    async def reconfigure(self, topic, message, reply):
        await super().reconfigure(topic, message, reply)
      
    async def process(self, topic, message, reply):
        if not message:
            log.error("received no data!")
            return

        tagged_frame = await self.tagger.tag_frame(message)
        await self.stream(f'Telemetry.AOS.VCID.{tagged_frame.vcid}.TaggedFrame', tagged_frame)

    async def supervisor_tree(self):
        async def monitor():
            while True:
                await self.publish('Bifrost.Monitors.Frames.Checks', self.tagger.subset_map())
                await asyncio.sleep(self.report_time)

        self.loop.create_task(monitor())
