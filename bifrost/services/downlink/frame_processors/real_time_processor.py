from bifrost.common.service import Service
from bifrost.common.loud_exception import with_loud_exception, with_loud_coroutine_exception
from bifrost.services.downlink.frame_processors.depacketizer import Depacketizer
from ait.core import log
import traceback
from bifrost.services.downlink.depacketizers.aos_to_ccsds import AOS_to_CCSDS_Depacketization


class RealTime_Telemetry_Frame_Processor(Service, Depacketizer):
    """
    Calls processor object and publish its publishables.
    """
    def __init__(self):
        Service.__init__(self)
        Depacketizer.__init__(self, AOS_to_CCSDS_Depacketization)
        self.vcid = 1
        self.processor_name = "Real Time Telemetry"
        self.start()

    async def process(self, topic, data, reply):
        log.debug(f"REAL TIME! {data.channel_counter}")
        try:
            tagged_packets = await self.depacketize(data)
            for tagged_packet in tagged_packets:
                subj = f'Telemetry.AOS.VCID.{tagged_packet.vcid}.TaggedPacket.{tagged_packet.packet_name}'
                await self.publish(subj,
                                   tagged_packet.subset_map())
            return
        except Exception as e:
            log.error(e)
            traceback.print_exc()
            raise e

    @with_loud_coroutine_exception
    async def reconfigure(self, topic, data, reply):
        self.pass_id = await self.config_request_pass_id()
        await super().reconfigure(topic, data, reply)
