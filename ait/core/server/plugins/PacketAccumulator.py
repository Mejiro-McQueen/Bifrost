from ait.core.server.plugins import Plugin
from gevent import Greenlet, sleep

from ait.core import log
import ait.dsn.plugins.Graffiti as Graffiti
from ait.dsn.plugins.TCTF_Manager import get_max_data_field_size, check_data_field_size

class PacketAccumulator(Plugin,
                        Graffiti.Graphable):
    def __init__(self, inputs=None, outputs=None, zmq_args=None, timer_seconds=1):
        super().__init__(inputs, outputs, zmq_args)

        self.packet_queue = []
        self.size_packet_queue_octets = 0
        self.glet = Greenlet.spawn(self.periodic_check)
        self.max_size_octets = get_max_data_field_size()
        self.timer_seconds = timer_seconds
        if not self.timer_seconds:
            log.warn(f"parameter timer_seconds was not providede in config.yaml")
        if self.timer_seconds < 1:
            self.timer_seconds = 1
            self.log.error(f"timer value {timer_seconds} must be greater "
                           f"than or equal to 1. Defaulting to {self.timer_seconds} seconds.")
        Graffiti.Graphable.__init__(self)

    def periodic_check(self):
        while True:
            sleep(self.timer_seconds)
            self.emit()

    def process(self, data, topic=None):
        if not data:
            log.error(f"received no data from {topic}.")

        if not check_data_field_size(data):
            log.error(f"initial payload from {topic} is oversized!")
            
        data_len = len(data)
        # Does not fit, need to emit
        if self.size_packet_queue_octets + data_len > self.max_size_octets:
            self.emit()
        # It fits! Add and defer emission
        self.packet_queue.append(data)
        self.size_packet_queue_octets += data_len

    def emit(self):
        if self.packet_queue:
            payload = self.packet_queue.pop(0)
            for i in self.packet_queue:
                payload += i
            if not check_data_field_size(payload):
                log.error("created oversized payload.")
            log.debug(f"publishing payload of size: {len(payload)}")
            self.publish(payload)
            self.size_packet_queue_octets = 0
            self.packet_queue.clear()

    def graffiti(self):
        n = Graffiti.Node(self.self_name,
                          inputs=[(i, "Command Packets") for i in self.inputs],
                          outputs=[],
                          label=f"Accumulate Command Packets\n Max Size: {self.max_size_octets}",
                          node_type=Graffiti.Node_Type.PLUGIN)
        return [n]
