from ait.core.server.plugins import Plugin
from gevent import Greenlet, sleep
import ait.dsn.plugins.TCTF_Manager as tctf

class PacketAccumulator(Plugin):
    def __init__(self, inputs=None, outputs=None, zmq_args=None, timer_seconds=1):
        super().__init__(inputs, outputs, zmq_args)
        
        self.log_header = __name__ + "->"
        self.packet_queue = []
        self.size_packet_queue_octets = 0
        self.glet = Greenlet.spawn(self.periodic_check)
        self.max_size_octets = tctf.get_max_data_field_size()
        self.timer_seconds = timer_seconds
        if not self.timer_seconds:
            log.warn(f"{self.log_header} parameter timer_seconds was not providede in config.yaml")            
        if self.timer_seconds < 1:
            self.timer_seconds = 1
            self.log.error(f"{self.log_header} timer value {timer_seconds} must be greater "
                           f"than or equal to 1. Defaulting to {self.timer_seconds} seconds.")

    def periodic_check(self):
        while True:
            sleep(self.timer_seconds)
            self.emit()

    def process(self, data, topic=None):
        if not data:
            log.error(f"{self.log_header} received no data from {topic}.")

        if not tctf.check_data_field_size(data):
            log.error(f"{self.log_header} initial payload from {topic} is oversized!")
            
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
            if not tctf.check_data_field_size(payload):
                log.error("{self.log_header} created oversized payload.")
            self.publish(payload)
            self.size_packet_queue_octets = 0
            self.packet_queue.clear()
