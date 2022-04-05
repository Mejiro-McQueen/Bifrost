from ait.core.server.plugins import Plugin
from ait.core import log

import ait.dsn.plugins.TCTF_Manager as tctf

class PacketPadder(Plugin):
    def __init__(self, inputs=None, outputs=None, zmq_args=None, **kwargs):
        super().__init__(inputs, outputs, zmq_args)
        self.logger_header = __name__ + " ->"
        self.size_pad_octets = tctf.get_max_data_field_size()

    def process(self, data, topic=None):
        if not data:
            log.error(f"{self.log_header} received no data from {topic}.")
        if not tctf.check_data_field_size(data):
            log.error(f"{self.log_header} initial data from {topic} is oversized.")
        if len(data) < self.size_pad_octets:
            fill = bytearray(self.size_pad_octets - len(data))
            data = data + fill
        if not tctf.check_data_field_size(data):
            log.error(f"{self.logger} created oversized data.")
        self.publish(data)

    def graffiti(self):
        self_name = type(self).__name__
        nodes = []
        labels = {}
        for i in self.inputs:
            labels[(i,self_name)] = "Unpadded Packet"
        labels[self_name] = (f"\t Pad Size Octets: {self.pad_octets}")
        node = Graffiti.Node(self_name, self.inputs, [], labels,
                             Graffiti.Node_Type.PLUGIN)
        nodes.append(node)
        return nodes
