from bifrost.common.service import Service
from bifrost.common.loud_exception import with_loud_exception
from bifrost.services.downlink.frame_processors.depacketizer import Frame_Depacketizer
from bifrost.services.downlink.depacketizers.aos_to_ccsds import AOS_to_CCSDS_Depacketization

from sunrise.depacketizers.sunrise_depacketizer import SunRISE_Depacketization
from bifrost.services.downlink.frame_processors.packet_tagger import CCSDS_Packet_Tagger
from ait.core import log
import traceback


class Stored_Telemetry_Frame_Processor(Service):
    """
    Calls stored telemetry processor object and publish its publishables.
    """
    def __init__(self):
        Service.__init__(self)
        self.vcid = 2
        self.processor_name = "Stored Time Telemetry"
        self.frame_depacketizer = Frame_Depacketizer(SunRISE_Depacketization,
                                                     self.processor_name)
        self.packet_tagger = CCSDS_Packet_Tagger(self.vcid,
                                                 self.processor_name)
        self.start()

    @with_loud_exception
    async def process(self, topic, data, reply):
        log.debug(f"STORED {data.channel_counter}")
        try:
            packets = self.frame_depacketizer(data)
            tagged_packets = self.packet_tagger(packets)
            for tagged_packet in tagged_packets:
                subj = f'Telemetry.AOS.VCID.{tagged_packet.vcid}.TaggedPacket.{tagged_packet.packet_name}'
                await self.publish(subj, tagged_packet.subset_map())
        except Exception as e:
            log.error(e)
            traceback.print_exc()
            raise e

    @with_loud_exception
    async def reconfigure(self, topic, data, reply):
        self.pass_id = await self.config_request_pass_id()
        await super().reconfigure(topic, data, reply)
