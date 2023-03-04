from bifrost.common.service import Service
from ait.core import log
import random


class Loss_Service(Service):
    def __init__(self):
        super().__init__()
        self.active = False
        self.percent = 0
        self.announce = False
        for i in range(0, 100):
            log.error("FRAME LOSS PLUGIN ACTIVE")
        self.start()

    async def process(self, topic, data, reply):
        if topic == 'LOSS_ACTIVATE':
            self.active = True
        elif topic == 'LOSS_DEACTIVATE':
            self.active = False
        elif topic == 'LOSS_CHANGE':
            self.percent = data
        elif topic == 'LOSS_ANNOUNCE':
            self.announce = data
        else:
            if self.active and self.percent >= random.uniform(0, 100):
                if self.announce:
                    log.error("Packet sent straight to burn in /dev/null!")
                    log.error(data)
                return
            else:
                await self.publish('Telemetry.AOS.Raw.Beef.Loss.Loss')
        return

    async def reconfigure(self, topic, message, reply):
        await super().reconfigure(topic, message, reply)
        return


class Corruption_Service(Service):
    def __init__(self):
        super().__init__()
        self.active = False
        self.percent = 0
        self.announce = False
        for i in range(0, 100):
            log.error("FRAME CORRUPTION PLUGIN ACTIVE")
        self.start()

    async def process(self, topic, data, reply):
        data = bytearray(data)
        if topic == 'CORRUPT_ACTIVATE':
            self.active = True
        elif topic == 'CORRUPT_DEACTIVATE':
            self.active = False
        elif topic == 'CORRUPT_CHANGE':
            self.percent = data
        elif topic == 'CORRUPT_ANNOUNCE':
            self.announce = data
        else:
            if self.active and self.percent >= random.uniform(0, 100) + random.random():
                index = random.randint(0, len(data) - 1)
                data[index] = random.getrandbits(1)
                if self.announce:
                    log.error("Packet Corrupted!!")
                    log.error(data)
            await self.publish('Telemetry.AOS.Raw.Beef.Loss.Corrupt')
        return

    async def reconfigure(self, topic, message, reply):
        await super().reconfigure(topic, message, reply)
        return
