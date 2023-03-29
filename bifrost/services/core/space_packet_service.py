from bifrost.common.service import Service
from bifrost.common.loud_exception import with_loud_coroutine_exception, with_loud_exception
from bifrost.common.ccsds_packet import Packet_State, CCSDS_Packet


class Space_Packet_Service(Service):
    @with_loud_exception
    def __init__(self):
        super().__init__()
        self.start()

    @with_loud_coroutine_exception
    async def packetize(self, topic, data, reply):
        self.publish(reply, CCSDS_Packet.encode(data))
        pass

    @with_loud_coroutine_exception
    async def depacketize(self, topic, data, reply):
        self.publish(reply, CCSDS_Packet.decode(data))
        pass

    @with_loud_coroutine_exception
    async def reconfigure(self, topic, message, reply):
        await super().reconfigure(topic, message, reply)
        return
