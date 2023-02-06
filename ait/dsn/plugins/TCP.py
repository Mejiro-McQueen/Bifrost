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
from colorama import Fore
import traceback

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
    hostname: str
    port: int
    mode: Mode
    read_queue: asyncio.Queue 
    write_queue: asyncio.Queue
    timeout_seconds: int = 5
    receive_size_bytes: int = 64000
    ip: str = field(init=False)
    log_header: str = field(init=False)

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
        asyncio.create_task(self.start())

    def __del__(self):
        self.shutdown()

    def shutdown(self):
        """
        Shutdown and close open socket, if any.
        """
        print(f"Shutting down {self}")
        if hasattr(self, 'writer'):
            self.writer.close()

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
                data = await self.write_queue.get()
                self.writer.write(data)
                await self.writer.drain()
                
            elif self.mode is Mode.RECEIVE:
                data = await self.reader.read(self.receive_size_bytes)
                await self.read_queue.put((self.topic, data))
                
                
    async def handle_client(self):
        self.reader, self.writer = \
            await asyncio.open_connection(self.hostname, self.port)
        while self.reader or self.writer:
            if self.mode is Mode.TRANSMIT:
                data = await self.write_queue.get()
                self.writer.write(data)
                await self.writer.drain()
                
            elif self.mode is Mode.RECEIVE:
                data = await self.reader.read(self.receive_size_bytes)
                await self.read_queue.put((self.topic, data))
                
                
    async def start(self):
        try:
            if self.hostname:
                print("Start client")
                await self.handle_client()
            else:
                print("Start server")
                await self.handle_server()
        except ConnectionRefusedError:
            log.error(f"Connection was refused for {self}.")
        except Exception as e:
            log.error(e)

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
        self.read_queue = asyncio.Queue()
        self.topic_subscription_map = defaultdict(list)
        self.loop.create_task(self.service_reads())
        self.configuration = defaultdict(dict)
        self.hot = False
        self.start()

    async def service_reads(self):
        while self.running:
            topic, msg = await self.read_queue.get()
            await self.stream(topic, msg)

    async def reconfigure(self, topic, message, reply):
        await super().reconfigure(topic, message, reply)

        def setup_subscriptions(subscription_map):
            for (server_name, metadata) in subscription_map.items():
                topic = metadata['topic']
                try:
                    sub = Subscription(server_name=server_name,
                                       topic=topic,
                                       hostname=metadata['hostname'],
                                       port=metadata['port'],
                                       mode=metadata['mode'],
                                       timeout_seconds=metadata['timeout_seconds'],
                                       read_queue=self.read_queue,
                                       write_queue=asyncio.Queue())
                    self.topic_subscription_map[topic].append(sub)
                except Exception as e:
                    log.error(f"Error initializing subscriptions: {e}")
                    traceback.print_exc()

        # def close_changed_connections(reconfiguration_map):
        #     for (server_name, metadata) in reconfiguration_map.items():
        #         print(Fore.CYAN, f"{self.topic_subscription_map=}", Fore.RESET)
        #         subs = self.topic_subscription_map.get(metadata['topic'])
        #         print(subs)
        #         for sub in subs:
        #             print("ZOING")
        #         #     log.info(f"Shutting down {sub}")
        #         #     sub.shutdown()            

        if self.hot:
            return
        subscription_map = {server: metadata for (server, metadata) in self.subscriptions.items()
                            if not metadata == self.configuration.get(server, {})}
        #close_changed_connections(subscription_map)
        setup_subscriptions(subscription_map)
        self.configuration = subscription_map
        self.hot = True
            
    async def process(self, topic, message, reply):
        """
        Send data to the transmit Subscriptions associated with topic.

        :returns: data from topic
        """
        if not message:
            log.info('Received no data')
            return
                
        if isinstance(message, CmdMetaData):
            message = message.payload_bytes

        write_queues = (i.write_queue for i in self.topic_subscription_map.get(topic, []))
        for write_queue in write_queues:
            await write_queue.put(message)
    
        if isinstance(message, CmdMetaData):
            await self.publish('Uplink.CmdMetaData.Complete', message)
    
    # def supervisor_tree(self, msg=None):
        
    #     def periodic_report(report_time=5):
    #         while True:
    #             time.sleep(report_time)
    #             msg = []
    #             for sub_list in self.topic_subscription_map.values():
    #                 msg += [i.status_map() for i in sub_list]
    #             log.debug(msg)
    #             self.stream(msg,  MessageType.TCP_STATUS.name)

    #     def high_priority(msg):
    #         # self.publish(msg, "monitor_high_priority_cltu")
    #         pass
        
    #     def monitor(restart_delay_s=5):
    #         # self.connect()
    #         # while True:
    #         #     time.sleep(restart_delay_s)
    #         #     if self.CLTU_Manager._state == 'active':
    #         #         log.debug(f"SLE OK!")
    #         #     else:
    #         #         self.publish("CLTU SLE Interface is not active!", "monitor_high_priority_cltu")
    #         #         self.handle_restart()
    #         pass

    #     if msg:
    #         high_priority(msg)
    #         return
           
    #     #if self.report_time_s:
    #         #reporter = Greenlet.spawn(periodic_report, self.report_time_s)
    #     #mon = Greenlet.spawn(monitor, self.restart_delay_s)
     
