from ait.core.server.plugins import Plugin
from ait.core import log
import ait.dsn.plugins.TCTF_Manager as tctf
import ait.dsn.plugins.Graffiti as Graffiti


class PacketPadder(Plugin,
                   Graffiti.Graphable):
    def __init__(self, inputs=None, outputs=None, zmq_args=None, **kwargs):
        super().__init__(inputs, outputs, zmq_args)
        self.logger_header = __name__ + " ->"
        self.size_pad_octets = tctf.get_max_data_field_size()
        Graffiti.Graphable.__init__(self)

    def graffiti(self):
        n = Graffiti.Node(self.self_name,
                          inputs=[(i, "Command Packets") for i in self.inputs],
                          outputs=[],
                          label="Pad Accumulation of Command Packets",
                          node_type=Graffiti.Node_Type.PLUGIN)
        return [n]
        
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
