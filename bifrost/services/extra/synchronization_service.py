from bifrost.common.service import Service
from ait.core import log
from dataclasses import dataclass, field
from colorama import Fore


@dataclass
class DeSyncResult():
    lead_fragment: bytes = b''  # Missed frame data, always useless other than debugging
    frames: list = field(default_factory=list)
    rear_fragment: bytes = b''  # Spanning Frame
    rear_fragment_required_length: int = 0
    rear_fragment_actual_length: int = 0

    def isNoBeefFound(self):
        res = all([self.lead_fragment, len(self.frames), self.rear_fragment])
        return res

    def __str__(self):
        s = f'{self.__class__.__name__} {Fore.RED} lead_fragment={self.lead_fragment}, {Fore.RESET} frames={self.frames},  {Fore.CYAN} rear_fragment={self.rear_fragment} {Fore.RESET} rear_fragment_actual_length={self.rear_fragment_actual_length}, rear_fragment_required_length={self.rear_fragment_actual_length}'
        return s


class SyncByte():
    def __init__(self, delimiter, length_size=4):
        self.sync = bytearray(delimiter)
        self.length_size = length_size

    def __call__(self, data):
        length = (len(data)).to_bytes(self.length_size, 'big')
        msg = self.sync + length + data
        return msg


class Synchronization(Service):
    def __init__(self):
        super().__init__()
        self.sync_obj = None
        self.start()
        return

    def process(self, topic, data, reply):
        msg = self.sync_obj(data.payload_bytes)
        data.payload_bytes = msg
        self.stream('Uplink.CmdMetaData.Sync', data)

    async def reconfigure(self, topic, message, reply):
        await super().reconfigure(topic, message, reply)
        self.sync_obj = SyncByte(self.syncbyte, 4)
        return


class DeSyncByte():
    def __int__(self):
        return

    @staticmethod
    def desync(data: bytes):
        data = bytearray(data)
        lead_fragment = None
        rear_fragment = None
        accum = []

        next_index = data.find(b'\xbe\xef')
        data = memoryview(data)
        if next_index == -1:
            return DeSyncResult(data, [], None)

        elif next_index != 0:
            lead_fragment = data[next_index:]

        data = data[next_index:]
        while data:
            data = data[2:]
            packet_length_bytes = data[:4]
            packet_length = int.from_bytes(data[0:4], 'big')
            data = data[4:]
            p = bytes(data[:packet_length])
            actual_length = len(p)

            if actual_length == packet_length:
                accum.append(p)
                data = data[actual_length:]

            elif actual_length < packet_length:
                rear_fragment = b'\xbe\xef' + packet_length_bytes + data
                break
            else:
                exit()
                pass

        res = DeSyncResult(lead_fragment, accum, rear_fragment)
        if rear_fragment:
            res.rear_fragment_required_length = packet_length
            res.rear_fragment_actual_length = actual_length - 4 - 2
        return res


class Desynchronization(Service):
    def __init__(self):
        super().__init__()
        self.desync_byte = DeSyncByte()
        self.rear_fragment = None
        self.synchronized = False
        self.strict = False
        self.last_rear_fragment_required_size = 0
        self.reset_counter = 0
        self.start()

    async def reconfigure(self, topic, message, reply):
        await super().reconfigure(topic, message, reply)
        return

    async def desynchronize(self, topic, data, reply):
        def monotonically_increasing_guard():
            if (self.last_rear_fragment_required_size and self.last_rear_fragment_required_size < res.rear_fragment_actual_length):
                # rear fragment definitely monotonically increasing
                self.reset_counter += 1
                if self.reset_counter == 2:
                    self.rear_fragment = None
                    self.reset_counter = 0
                    self.synchronized = False
            return
            
        if self.rear_fragment:
            data = self.rear_fragment + data
            self.rear_fragment = None
            #log.info(f"RESTORED FRAGMENTED FRAME!")

        res = self.desync_byte.desync(data)
        self.rear_fragment = res.rear_fragment
        monotonically_increasing_guard()
        self.last_rear_fragment_required_size = res.rear_fragment_actual_length
        
        if res.frames and not self.synchronized:
            log.info(f"{Fore.GREEN} Synchronized {Fore.RESET}")
            self.synchronized = True

        elif res.isNoBeefFound() and self.synchronized:
            log.error(f"No beef was found in data. What gives?")
            log.error(f"Synchronization was lost?")
            self.synchronized = False
            self.rear_fragment = None
            if self.strict:
                exit()

        elif res.lead_fragment and self.synchronized:
            log.error(f"Synchronization was lost?")
            self.rear_fragment = None
            self.synchronized = False
            data = None
            if self.strict:
                exit()

        elif self.synchronized:
            for i in res.frames:
                self.reset_counter = 0
                res = await self.stream('Telemetry.AOS.Raw', i)
        else:
            #self.rear_fragment = None
            #self.synchronized = False
            pass
