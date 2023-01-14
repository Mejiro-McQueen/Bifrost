import selectors
from ait.core.server import Plugin
from ait.core import log
from collections import defaultdict
from dataclasses import dataclass, field
import enum
import errno

from ait.core.message_types import MessageType
from sunrise.CmdMetaData import CmdMetaData
import asyncio
from time import sleep


class Mode(enum.Enum):
    TRANSMIT = enum.auto()
    RECEIVE = enum.auto()



@dataclass
class Subscription:
    """
    Creates subscription.
    ip, socket, and log_header are derrived from the mandatory fields.
    """
    server_name: str
    topic: str
    routing_key: str
    hostname: str
    port: int
    mode: Mode
    timeout_seconds: int = 5
    receive_size_bytes: int = 64000
    ip: str = field(init=False)
    log_header: str = field(init=False)
    data_queue: asyncio.Queue = asyncio.Queue() 

    def __post_init__(self):
        """
        Sets up client/server sockets.
        Derrives IP from hostname, if provided in config.
        """
        self.ip = None
        self.log_header = f":-> {self.server_name} :=>"
        self.mode = Mode[self.mode]
        self.sent_counter = 0
        self.receive_counter = 0

    def __del__(self):
        """
        Shutdown and close open socket, if any.
        """
        if hasattr(self, 'writer'):
            self.writer.close()
        if hasattr(self, 'reader'):
            self.reader.close()

    def status_map(self):
        m = {'topic': self.topic,
             'host': self.hostname, 
             'port': self.port,
             'mode': self.mode.name, 
             'Tx_Count': self.sent_counter,
             'Rx_Count': self.receive_counter}
        return m

    async def handle_server(self):
        self.reader, self.writer = \
            await asyncio.start_server(self.hostname, self.port)

        while self.reader or self.writer:
            if self.mode is Mode.TRANSMIT:
                data = await self.data_queue.get()
                self.writer.write(data)
                await self.writer.drain()
            elif self.mode is Mode.RECEIVE:
                data = await self.reader.read(self.receive_size_bytes)
                await self.rabbit_publish(self.topic, self.routing_key, data)
        
    async def handle_client(self):
        self.reader, self.writer = \
            await asyncio.open_connection(self.hostname, self.port)
        while self.reader or self.writer:
            if self.mode is Mode.TRANSMIT:
                data = await self.data_queue.get()
                self.writer.write(data)
                await self.writer.drain()
            elif self.mode is Mode.RECEIVE:
                data = await self.reader.read(self.receive_size_bytes)
                await self.rabbit_publish(self.topic, self.routing_key, data)
                
    async def start(self, rabbit_publish):
        print("I'M UP!")
        self.rabbit_publish = rabbit_publish
        if self.hostname:
            await self.handle_client()
        else:
            await self.handle_server()

class TCP_Manager(Plugin):
    """
    Customize the template within the config.yaml plugin block:


    - plugin:
        name: ait.dsn.plugins.TCP.TCP_Manager
        inputs:
            - PUB_SUB_TOPIC_1
            - PUB_SUB_TOPIC_2
        subscriptions:
            PUB_SUB_TOPIC_1:
                Server_Name1:
                    port: 42401
                    timeout: 1
                    mode: TRANSMIT
                Server_Name2:
                    port: 42401
                    hostname: someserver.xyz
                    mode: TRANSMIT
            PUB_SUB_TOPIC_3_RECEIVE:
                Server_Name3:
                    port: 12345
                    receive_size_bytes: 1024
                    mode: RECEIVE
                Server_Name4:
                    port: 12346
                    host: localhost
                    receive_size_bytes: 512
                    mode: RECEIVE

    See documentation for more details.
    """

    def __init__(self):
        """
        Create Subscriptions based on config.yaml entries.
        Forks a process to handle receiving subscriptions.
        Creates auxillary socket maps and lists.
        """
        super().__init__()
        self.tasks = []
        self.cancel = True
        #a = self.loop.create_task(self.service_read_sockets())
        self.start()
    
        #self.supervisor_tree = Greenlet.spawn(self.supervisor_tree)
        #Graffiti.Graphable.__init__(self)

    async def reconfigure(self, message):
        await super().reconfigure(message)
        print(f'{message=}')
        self.topic_subscription_map = defaultdict(list)

        self.tasks = []
        for (server_name, metadata) in self.subscriptions.items():
            sub = Subscription(server_name=server_name, **metadata)
            self.topic_subscription_map[metadata['routing_key']].append(sub)
            self.tasks.append(sub.start(self.rabbit_publish))
            await asyncio.create_task(sub.start(self.rabbit_publish))
            await self.rabbit_queue_bind(sub.topic, sub.routing_key, sub.routing_key)
        print(f'LETS GO! {self.tasks=}')
        self.cancel = True

    async def service_read_sockets(self):
        print('fig')
        while True:
            print("ZOZ")
            if self.cancel:
                while self.tasks:
                    task = self.tasks.pop()
                    await task.cancel()
            asyncio.gather(*self.tasks)
            self.cancel = False
            await asyncio.sleep(5)
                
            
    def process(self, data, topic=None):
        """
        Send data to the transmit Subscriptions associated with topic.

        :returns: data from topic
        """
        if not data:
            log.info('Received no data')
            return
        subs = self.topic_subscription_map[topic]
        subs = [sub for sub in subs if sub.mode is Mode.TRANSMIT]
        for sub in subs:
            if isinstance(data, CmdMetaData):
                sub.data_queue.put(data.payload_bytes)
            else:
                sub.data_queue.put(data)
        
        # if isinstance(data, CmdMetaData):
        #     self.publish(data, MessageType.CL_UPLINK_COMPLETE.name)
        # return data

    # def graffiti(self):
    #     nodes = []

    #     n = Graffiti.Node(self.self_name,
    #                       inputs=[(i, "PUB/SUB Message") for i in self.inputs],
    #                       outputs=[],
    #                       label="",
    #                       node_type=Graffiti.Node_Type.PLUGIN)

    #     nodes.append(n)

    #     for (topic, subs) in self.topic_subscription_map.items():
    #         for sub in subs:
    #             if sub.mode is Mode.TRANSMIT:
    #                 n = Graffiti.Node(self.self_name,
    #                                   inputs=[],
    #                                   outputs=[(sub.hostname,
    #                                             f"{sub.topic}\n"
    #                                             f"Port: {sub.port}")],
    #                                   label="Manage TCP Transmit and Receive",
    #                                   node_type=Graffiti.Node_Type.TCP_SERVER)

    #             else:  # sub.mode is Mode.RECEIVE:
    #                 n = Graffiti.Node(self.self_name,
    #                                   inputs=[(sub.hostname,
    #                                            f"{sub.topic}\n"
    #                                            f"Port: {sub.port}")],
    #                                   outputs=[(sub.topic, "Bytes"),],
    #                                   label="Manage TCP Transmit and Receive",
    #                                   node_type=Graffiti.Node_Type.TCP_CLIENT)
    #             nodes.append(n)
                
    #     n = Graffiti.Node(self.self_name,
    #                       inputs=[],
    #                       outputs=[(MessageType.TCP_STATUS.name,
    #                                 MessageType.TCP_STATUS.value)],
    #                       label="Manage TCP Transmit and Receive",
    #                       node_type=Graffiti.Node_Type.TCP_CLIENT)
    #     nodes.append(n)
    #     return nodes
    
    def supervisor_tree(self, msg=None):
        
        def periodic_report(report_time=5):
            while True:
                time.sleep(report_time)
                msg = []
                for sub_list in self.topic_subscription_map.values():
                    msg += [i.status_map() for i in sub_list]
                log.debug(msg)
                self.publish(msg,  MessageType.TCP_STATUS.name)

        def high_priority(msg):
            # self.publish(msg, "monitor_high_priority_cltu")
            pass
        
        def monitor(restart_delay_s=5):
            # self.connect()
            # while True:
            #     time.sleep(restart_delay_s)
            #     if self.CLTU_Manager._state == 'active':
            #         log.debug(f"SLE OK!")
            #     else:
            #         self.publish("CLTU SLE Interface is not active!", "monitor_high_priority_cltu")
            #         self.handle_restart()
            pass

        if msg:
            high_priority(msg)
            return
           
        #if self.report_time_s:
            #reporter = Greenlet.spawn(periodic_report, self.report_time_s)
        #mon = Greenlet.spawn(monitor, self.restart_delay_s)
     
