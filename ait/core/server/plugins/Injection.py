from ait.core.server.plugins import Plugin
from ait.core import log
from gevent import Greenlet
import ait.dsn.plugins.Graffiti as Graffiti
import pprint


class file_injector():

    def __init__(self, publish, path, topic, loop=False):
        self.path = path
        self.topic = topic
        self.loop = loop
        self.publish = publish

    def __repr__(self):
        a = (f"Topic: {self.topic}, Path: {self.path}, Loop: {self.loop}")
        return a
    
    def run(self):
        while True:
            with open(self.path, 'rb') as reader:
                for line in reader.readlines():
                    line = bytes(line.rstrip())
                    self.publish(line, self.topic)
                if not self.loop:
                    return


class Inject_File(Plugin):
    def __init__(self, inputs=None, outputs=None, zmq_args=None, subscriptions=None, **kwargs):
        super().__init__(inputs, outputs, zmq_args)
        self.injectors = []
        for (topic, opts) in subscriptions.items():
            path = opts.get('path')
            loop = opts.get('loop')
            obj = file_injector(self.publish, path, topic, loop)
            self.injectors.append(obj)
        self.once = True
        Graffiti.wait(self)

    def graffiti(self):
        self_name = type(self).__name__
        nodes = []
        labels = {}
        injectors_label = pprint.pformat(self.injectors, width=-1)
        labels[self_name] = f"\t {injectors_label}\n"
        node = Graffiti.Node(self_name, [], [], labels,
                             Graffiti.Node_Type.PLUGIN)
        nodes.append(node)
        return nodes

    def process(self, data, topic=None):
        if self.once:
            self.once = False
            self.greenlets = []
            for i in self.injectors:
                g = Greenlet.spawn(i.run)
                self.greenlets.append(g)
