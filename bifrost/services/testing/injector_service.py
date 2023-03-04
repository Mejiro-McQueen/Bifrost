from bifrost.common.service import Service
from pathlib import Path
from bifrost.services.extra.synchronization_service import SyncByte
from bifrost.common.loud_exception import with_loud_exception, with_loud_coroutine_exception
from tqdm import tqdm
import os
import asyncio

class Data_Injection_Service(Service):

    @with_loud_exception
    def __init__(self):
        super().__init__()
        self.start()

    @with_loud_coroutine_exception
    async def reconfigure(self, topic, message, reply):
        await super().reconfigure(topic, message, reply)

    @with_loud_coroutine_exception
    async def inject_binary_stream(self, topic, message, reply):
        stream = message['stream']
        f = Path(message['local_path'])
        if not f.exists:
            return
        size = os.path.getsize(f)
        t = tqdm(total=size, unit='B', unit_scale=True, unit_divisor=1024, desc=f'Injecting binary {f} into {stream}')
        chunk = 2000
        with f.open('rb') as f:
            while (data := f.read(chunk)):
                await self.stream(stream, data)
                t.update(chunk)
                #await asyncio.sleep(0.01)
        t.close()
