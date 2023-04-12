from bifrost.common.service import Service
from bifrost.common.loud_exception import with_loud_coroutine_exception, with_loud_exception
from bifrost.common.disk_writer import Disk_Writer
import asyncio


class Monitor(Service):
    @with_loud_exception
    def __init__(self):
        super().__init__()
        self.loop.create_task(self.periodic_report())
        self.report_time = 5
        self.start()

    @with_loud_coroutine_exception
    async def process(self, topic, data, reply):
        self.data_map[topic] = data

    @with_loud_exception
    async def periodic_report(self):
        while True:
            self.disk_writer.write_to_disk(self.data_map)
            await asyncio.sleep(self.report_time)

    @with_loud_coroutine_exception
    async def reconfigure(self, topic, message, reply):
        self.data_map = {}
        self.pass_id = await self.config_request("global.mission.pass_id")
        self.downlink_path = await self.config_request_downlink_path()
        self.sv_name = await self.config_request('instance.space_vehicle.sv_name')
        self.disk_writer = Disk_Writer("../monitors", "", 'monitors',
                                       self.pass_id, self.downlink_path, self.sv_name)
        await super().reconfigure(topic, message, reply)
        return
