from gevent import time, Greenlet, monkey
monkey.patch_all()
import ait.core
import ait.dsn.sle
import ait.dsn.sle.cltu
from ait.core.server.plugins import Plugin
from ait.core import log
from ait.core.message_types import MessageType
import ait.dsn.plugins.Graffiti as Graffiti


class send_CLTU(Plugin,Graffiti.Graphable):
    def __init__(self, inputs=None, outputs=None,
                 zmq_args=None, report_time_s=0, autorestart=True, **kwargs):
        inputs = ['SLE_CLTU_RESTART',
                  'SLE_CLTU_STOP',
                  'create_CLTU']
        super().__init__(inputs, outputs, zmq_args)
        self.restart_delay_s = 5
        self.CLTU_Manager = None
        self.supervisor = Greenlet.spawn(self.supervisor_tree)
        self.report_time_s = report_time_s
        Graffiti.Graphable.__init__(self)
        self.send_counter = 0
        self.autorestart = autorestart


    def connect(self):
        log.info(f"Starting CLTU interface.")
        try:
            self.CLTU_Manager = ait.dsn.sle.cltu.CLTU()
            self.CLTU_Manager.connect()
            time.sleep(5)
            self.CLTU_Manager.bind()
            time.sleep(5)
            self.CLTU_Manager.start()
            time.sleep(5)

            if self.CLTU_Manager._state == 'active':
                msg = f"New Connection: CLTU interface is {self.CLTU_Manager._state}!"
                log.info(msg)
            else:
                msg = "CLTU Interface encountered an error during startup."
                log.error(msg)
            self.supervisor_tree(msg)

        except Exception as e:
            msg = f"CLTU SLE Interface Encountered exception {e}."
            log.error(msg)
            self.supervisor_tree(msg)

    def handle_restart(self):
        self.sle_stop()
        self.connect()

    def sle_stop(self):
        if self.CLTU_Manager:
            self.CLTU_Manager.shutdown(unbind=False)
            time.sleep(self.restart_delay_s)

    def supervisor_tree(self, msg=None):
        
        def periodic_report(report_time=5):
            msg = {'state': None,
                   'total_sent': None}
            while True:
                time.sleep(report_time)
                msg['total_sent'] = self.send_counter
                if self.CLTU_Manager:
                    msg['state'] = self.CLTU_Manager._state
                self.publish(msg, MessageType.CLTU_STATUS.name) 
                log.debug(f"{msg}")

        def high_priority(msg):
            self.publish(msg, MessageType.HIGH_PRIORITY_CLTU_STATUS.name)
                                 
        def monitor(restart_delay_s=5):
            if self.autorestart:
                log.info("Initial start of CLTU interface")
                self.handle_restart()
            while True:
                time.sleep(restart_delay_s)
                if self.CLTU_Manager and self.CLTU_Manager._state == 'active':
                    log.debug(f"SLE OK!")
                elif not self.autorestart:
                    continue
                else:
                    
                    msg = ("Response not received from CLTU SLE responder " 
                           "during bind request. Bind unsuccessful")
                    high_priority(f"CLTU interface is {self.CLTU_Manager._state}!")
                    high_priority(msg)
                    log.error(msg)
                    self.handle_restart()

        if msg:
            high_priority(msg)
            return
        
        if self.report_time_s:
            reporter = Greenlet.spawn(periodic_report, self.report_time_s)
        mon = Greenlet.spawn(monitor, self.restart_delay_s)
        
    def process(self, data, topic=None):
        if topic == 'SLE_CLTU_RESTART':
            log.info("Received CLTU Restart Directive!")
            self.handle_restart()
            return
        elif topic == 'SLE_CLTU_STOP':
            log.info("Received CLTU Stop Directive!")
            self.sle_stop()
            return

        else:
            try:
                self.CLTU_Manager.upload_cltu(data.payload_bytes)
                self.send_counter += 1
                self.publish(data)
                ait.core.log.debug("uploaded CLTU")

            except Exception as e:
                log.error(f"Encountered exception {e}.")
                self.handle_restart()

    def graffiti(self):
        n = Graffiti.Node(self.self_name,
                          inputs=[(i, "CLTU")
                                  for i in self.inputs],
                          outputs=[("SLE Interface", "CLTU"),
                                   (MessageType.CLTU_STATUS.name,
                                    MessageType.CLTU_STATUS.value),
                                   (MessageType.HIGH_PRIORITY_CLTU_STATUS.name,
                                    MessageType.HIGH_PRIORITY_CLTU_STATUS.value)],
                          label=("Forwards CLTU to SLE Interface"),
                          node_type=Graffiti.Node_Type.PLUGIN)
        return [n]
