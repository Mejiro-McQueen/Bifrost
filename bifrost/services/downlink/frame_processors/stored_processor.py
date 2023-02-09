from bifrost.common.service import Service
from bifrost.common.loud_exception import with_loud_exception
from bifrost.services.downlink.frame_processors.depacketizer import Depacketizer
from bifrost.services.downlink.depacketizers.aos_to_ccsds import AOS_to_CCSDS_Depacketization
from ait.core import log


class Stored_Telemetry_Frame_Processor(Service, Depacketizer):
    """
    Calls stored telemetry processor object and publish its publishables.
    """
    def __init__(self):
        Service.__init__(self)
        Depacketizer.__init__(self, AOS_to_CCSDS_Depacketization)
        self.vcid = 2
        self.processor_name = "Stored Time Telemetry"
        self.start()

    @with_loud_exception
    async def process(self, topic, data, reply):
        log.debug(f"STORED {data.channel_counter}")
        tagged_packets = await self.depacketize(data)
        for tagged_packet in tagged_packets:
            subj = f'Telemetry.AOS.VCID.{tagged_packet.vcid}.TaggedPacket.{tagged_packet.packet_name}'
            await self.publish(subj, tagged_packet.subset_map())

    @with_loud_exception
    async def reconfigure(self, topic, data, reply):
        self.pass_id = await self.config_request_pass_id()
        await super().reconfigure(topic, data, reply)
