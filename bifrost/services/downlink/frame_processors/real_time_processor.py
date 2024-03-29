from bifrost.common.service import Service
from bifrost.common.loud_exception import with_loud_exception, with_loud_coroutine_exception
from bifrost.services.downlink.frame_processors.depacketizer import Frame_Depacketizer
from ait.core import log
import traceback

from bifrost.services.downlink.depacketizers.aos_to_ccsds import AOS_to_CCSDS_Depacketization
from bifrost.services.downlink.frame_processors.packet_tagger import CCSDS_Packet_Tagger
from bifrost.common.time_utility import time_processed


class RealTime_Telemetry_Frame_Processor(Service):
    """
    Depacketize frames
    Tag packets
    """
    @with_loud_exception
    def __init__(self):
        Service.__init__(self)
        self.vcid = 0
        self.processor_name = "Real Time Telemetry"
        self.enforce_sequence = False
        self.secondary_header_length = 6 # Length of CCSDS Space Packet Secondary Header
        self.frame_depacketizer = Frame_Depacketizer(AOS_to_CCSDS_Depacketization,
                                                     self.processor_name,
                                                     self.enforce_sequence,
                                                     self.secondary_header_length)
        self.start()

    @with_loud_coroutine_exception
    async def process(self, topic, data, reply):
        log.debug(f"REAL TIME! {data['channel_counter']}")
        try:
            ccsds_packets = self.frame_depacketizer(data) # Can be a lot of nones, fix in depacketizer
            tagged_packets = self.packet_tagger(ccsds_packets)
            for tagged_packet in tagged_packets:
                vcid = tagged_packet['vcid']
                packet_name = tagged_packet['packet_name']
                subj = f"Telemetry.AOS.VCID.{vcid}.TaggedPacket"
                await self.publish(f'{subj}.{packet_name}', tagged_packet)
                await self.stream(f'{subj}.Decoded', tagged_packet)
                
        except Exception as e:
            log.error(e)
            traceback.print_exc()
            raise e

    @with_loud_coroutine_exception
    async def reconfigure(self, topic, data, reply):
        self.pass_id = await self.config_request_pass_id()
        self.sv_identifier = await self.config_request_value('instance.space_vehicle.identifier')
        await super().reconfigure(topic, data, reply)
        self.packet_tagger = CCSDS_Packet_Tagger(self.vcid,
                                                 self.processor_name,
                                                 time_processed,
                                                 self.pass_id,
                                                 self.sv_identifier)

