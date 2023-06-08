from bifrost.common.service import Service
from bifrost.common.loud_exception import with_loud_coroutine_exception, with_loud_exception
from bifrost.common.ccsds_packet import Packet_State, CCSDS_Packet

class Space_Packet_Service(Service):
    @with_loud_exception
    def __init__(self):
        super().__init__()
        self.start()

    @with_loud_coroutine_exception
    async def packetize_cmd_metadata(self, topic, data, reply):
        payload = CCSDS_Packet.encode(data['payload_bytes'], data['apid'])
        data['payload_bytes'] = payload
        if reply:
            await self.publish(reply, data)
        else:
            await self.stream('Uplink.CmdMetaData.Space_Packet', data)

    @with_loud_coroutine_exception
    async def packetize_raw(self, topic, data, reply):
        # This does not belong in a pipeline, so always publish via reply
        res = CCSDS_Packet.encode(data)
        await self.publish(reply, res)

    @with_loud_coroutine_exception
    async def depacketize(self, topic, data, reply):
        if reply:
            # Service Reply
            await self.publish(reply, CCSDS_Packet.decode(data))
        else:
            # Pipeline Publish
            pass

    @with_loud_coroutine_exception
    async def reconfigure(self, topic, message, reply):
        await super().reconfigure(topic, message, reply)
        return
