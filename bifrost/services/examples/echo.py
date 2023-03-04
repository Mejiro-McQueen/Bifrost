from bifrost.common.service import Service
import asyncio


class Echo(Service):

    def __init__(self):
        super().__init__() # Setup RabbitMQ and Subscribe for autoconfig
        #pending = io.Task.all_tasks()
        #self.loop.run_until_complete(io.gather(*pending))
        self.start()

    async def reconfigure(self, topic, data, reply):
        # Accept ther reconfig message, config yaml is in body
        #print(f'Got Reconfig {message=}')
        # Apply standard reconfig
        await super().reconfigure(topic, data, reply)
        return

    async def echo_alice(self, topic, data, reply):
        #print(f'{channel=} {method=} {properties=} {body=}')
        print(f'Alice {" ".join(data)}')

    async def echo_bob(self, topic, data, reply):
        print(f'Bob {" ".join(data)}')

    async def echo_mr_x(self, topic, data, reply):
        print(f'FOR YOUR EYES ONLY: {data}')

    async def echo_everyone(self, topic, data, reply):
        print(f'Hello!')


class Hello(Service):
    def __init__(self):
        self.mr_x = "It's a mystery"
        self.sleep = 1
        super().__init__()
        self.loop.create_task(self.produce())
        self.start()

    async def produce(self):
        while self.running:
            # Say something to Alice and Bob
            await self.publish('Hello.Bob',
                               ['The Builder'])
            await self.publish('Hello.Alice',
                               ['In', 'Wonderland'])
            await self.publish('Hello.Mr_x',
                               str(self.mr_x))
            await asyncio.sleep(self.sleep)

    async def reconfigure(self, topic, data, reply):
        # We don't do much, so we just use the standard reconfigure
        await super().reconfigure(topic, data, reply)
        return
