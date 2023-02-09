from bifrost.common.service import Service
from bifrost.common.disk_writer import Disk_Writer
import asyncio


class Monitor(Service):
    def __init__(self):
        super().__init__()
        self.data_map = {}
        self.report_time = 5
        self.disk_writer = Disk_Writer("../monitors", "", 'monitors')
        self.loop.create_task(self.periodic_report())
        self.start()

    async def process(self, topic, data, reply):
        self.data_map[topic] = data

    async def periodic_report(self):
        while True:
            self.disk_writer.write_to_disk(self.data_map)
            await asyncio.sleep(self.report_time)
