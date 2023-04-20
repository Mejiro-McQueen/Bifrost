from bifrost.common.service import Service
from bifrost.common.loud_exception import with_loud_exception, with_loud_coroutine_exception
from ait.core import log
from collections import defaultdict
from dataclasses import dataclass, field
import enum
from bifrost.services.core.commanding.cmd_meta_data import CmdMetaData
import asyncio
import traceback
import socket
import ipaddress
from colorama import Fore


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

    @with_loud_exception
    def __post_init__(self):
        """
        Sets up client/server sockets.
        Derrives IP from hostname, if provided in config.
        """
        self.ip = None
        self.log_header = f":-> {self.server_name} :=>"
        if self.hostname:
            try:
                #Hostname is an ip
                ipaddress.ip_address(self.hostname)
                self.ip = self.hostname
                self.hostname = socket.gethostbyaddr(self.hostname)
            except Exception as e:
                # Hostname is a hostname
                self.ip = socket.gethostbyname(self.hostname)
        else:
            self.socket = self.setup_server_socket()
        self.mode = Mode[self.mode]
        self.sent_counter = 0
        self.receive_counter = 0
        self.task = asyncio.create_task(self.start())

    @with_loud_exception
    def shutdown(self):
        """
        Shutdown and close open socket, if any.
        """
        log.info(f"{Fore.YELLOW}Shutting down {self.server_name} {Fore.RESET}")
        if hasattr(self, 'writer'):
            self.writer.close()
            self.writer = None
        if hasattr(self, 'reader'):
            self.reader = None
        try:
            self.task.cancel()
        except asyncio.CancelledError:
            # We're fine
            pass

    def status_map(self):
        m = {'topic': self.topic,
             'host': self.hostname,
             'port': self.port,
             'mode': self.mode.name,
             'Tx_Count': self.sent_counter,
             'Rx_Count': self.receive_counter}
        return m

#    @with_loud_coroutine_exception
    async def handle_server(self):
        self.reader, self.writer = await asyncio.start_server(self.hostname, self.port)
        while self.reader or self.writer:
            if self.mode is Mode.TRANSMIT:
                data = await self.write_queue.get()
                self.writer.write(data)
                await self.writer.drain()
                self.sent_counter += 1

            elif self.mode is Mode.RECEIVE:
                data = await self.reader.read(self.receive_size_bytes)
                await self.read_queue.put((self.topic, data))
                self.receive_counter += 1

#    @with_loud_coroutine_exception
    async def handle_client(self):
        self.reader, self.writer = await asyncio.open_connection(self.hostname, self.port)
        log.info(f"{Fore.GREEN}Connection to {self.server_name} is ready. {Fore.RESET}")
        while self.reader or self.writer:
            if self.mode is Mode.TRANSMIT:
                data = await self.write_queue.get()
                self.writer.write(data)
                await self.writer.drain()
                self.sent_counter += 1

            elif self.mode is Mode.RECEIVE:
                data = await self.reader.read(self.receive_size_bytes)
                await self.read_queue.put((self.topic, data))
                self.receive_counter += 1

    @with_loud_coroutine_exception
    async def start(self):
        try:
            if self.hostname:
                log.info("Starting client on {self.hostname}:{self.port}")
                await self.handle_client()
            else:
                log.info("Starting server on {self.hostname}:{self.port}")
                await self.handle_server()
        except ConnectionRefusedError:
            log.error(f"Connection was refused for {self.hostname}:{self.port}.")
            await asyncio.sleep(5)
            await self.start()
        except socket.error:
            log.error(f'Could not establish connection for on {self.hostname}:{self.port}')
            await asyncio.sleep(5)
            await self.start()
        except Exception as e:
            log.error(e)
            await asyncio.sleep(5)
            await self.start()


class TCP_Manager(Service):
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

    @with_loud_exception
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
        self.report_time = 5
        self.loop.create_task(self.supervisor_tree())
        self.start()

    @with_loud_coroutine_exception
    async def service_reads(self):
        while self.running:
            topic, msg = await self.read_queue.get()
            await self.stream(topic, msg)

    @with_loud_exception
    def setup_subscription(self, subscription_map):
        metadata = subscription_map
        topic = metadata['topic']
        server_name = metadata['server_name']
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
            self.configuration[server_name] = metadata
        except Exception as e:
            log.error(f"Error initializing subscriptions: {e}")
            traceback.print_exc()

    @with_loud_exception
    async def reconfigure(self, topic, message, reply):
        await super().reconfigure(topic, message, reply)
        desired_subscription_map = {server: metadata for (server, metadata) in self.subscriptions.items()}
        for (server_name, metadata) in desired_subscription_map.items():
            metadata['server_name'] = server_name

        for (k, v) in self.topic_subscription_map.items():
            kill = [i for i in v if i.server_name not in desired_subscription_map]
            preserve = [i for i in v if i not in kill]
            for i in kill:
                i.shutdown()
            self.topic_subscription_map[k] = preserve

        new_subscription_map = {server: metadata for (server, metadata) in self.subscriptions.items()
                                if not metadata == self.configuration.get(server, {})}

        for (server_name, metadata) in new_subscription_map.items():
            self.setup_subscription(metadata)
        self.configuration = desired_subscription_map

    @with_loud_exception
    def disconnect_host(self, server_name):
        # Maybe easier to internally adjust config and force a reconfig?
        found = False
        for (k, v) in self.topic_subscription_map.items():
            for i in v:
                if i.server_name == server_name:
                    found = True
                    i.shutdown()
                    v.remove(i)
                    break

        self.configuration.pop(server_name, None)
        return found

    @with_loud_coroutine_exception
    async def process(self, topic, message, reply):
        """
        Send data to the transmit Subscriptions associated with topic.

        :returns: data from topic
        """
        if not message:
            log.info('Received no data')
            return

        if isinstance(message, CmdMetaData):
            pl = message.payload_bytes
        else:
            pl = message

        write_queues = (i.write_queue for i in self.topic_subscription_map.get(topic, []))
        for write_queue in write_queues:
            await write_queue.put(pl)

        if isinstance(message, CmdMetaData):
            await self.publish('Uplink.CmdMetaData.Complete', message)

    @with_loud_coroutine_exception
    async def directive_reconnect(self, topic, message, reply):
        config = self.configuration.get(message, None)
        if not config:
            data = 'Error, Could not find config for host: {message}'
            await self.publish(reply, data)
            return

        await self.directive_disconnect(topic, message, None)

        self.setup_subscription(config)
        data = f'Ok, connected {config["server_name"]}'
        await self.publish(reply, data)

    @with_loud_coroutine_exception
    async def directive_disconnect(self, topic, message, reply):
        if self.disconnect_host(message):
            data = f'OK, disconnect host: {message}'
        else:
            data = f'Could not find host {message}'
        await self.publish(reply, data)

    @with_loud_coroutine_exception
    async def directive_connect(self, topic, message, reply):
        try:
            self.setup_subscription(message)
            data = f'OK, connect to {message["server_name"]}'
        except Exception as e:
            data = f'Error, {e}'
        await self.publish(reply, data)

    @with_loud_coroutine_exception
    async def directive_config(self, topic, message, reply):
        data = self.configuration
        await self.publish(reply, data)

    @with_loud_coroutine_exception
    async def supervisor_tree(self, msg=None):
        async def monitor():
            while True:
                await asyncio.sleep(self.report_time)
                msg = []
                for sub_list in self.topic_subscription_map.values():
                    msg += [i.status_map() for i in sub_list]
                if msg:
                    await self.publish('Bifrost.Monitors.TCP_STATUS', msg)

        self.loop.create_task(monitor())


# TODO Restore timeout option
