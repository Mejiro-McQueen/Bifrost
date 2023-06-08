from bifrost.common.service import Service
from bifrost.common.loud_exception import with_loud_coroutine_exception, with_loud_exception
from ait.core import log
from ait.dsn.sle.cltu import CLTU
import asyncio
import ait

"""
A plugin which creates an CLTU connection with the DSN.
Frames received via the CLTU connection are sent to the output stream
"""


class SLE_CLTU_Uplink_Service(Service):
    @with_loud_exception
    def __init__(self):
        super().__init__()
        self.send_counter = 0
        self.restart_delay_s = 5
        self.report_time_s = 5
        self.autorestart = False
        self.cltu_object = None
        self.loop.create_task(self.monitor())
        self.loop.create_task(self.supervisor())
        self.start()

    @with_loud_coroutine_exception
    async def reconfigure(self, topic, message, reply):
        await super().reconfigure(topic, message, reply)
        self.output_queue = asyncio.Queue()
        return

    @with_loud_coroutine_exception
    async def directive_stop_sle(self, topic, message, reply):
        msg = "Received CLTU Stop Directive!"
        log.info(msg)
        await self.publish("Bifrost.Messsages.Info.SLE.CLTU", msg)
        await self.sle_stop()
        return

    @with_loud_coroutine_exception
    async def directive_restart_sle(self, topic, message, reply):
        msg = "Received CLTU restart Directive!"
        log.info(msg)
        await self.publish("Bifrost.Messsages.Info.SLE.CLTU", msg)
        await self.sle_stop()
        await asyncio.sleep(2)
        await self.handle_restart()

    @with_loud_coroutine_exception
    async def connect(self):
        msg = "Starting CLTU interface."
        log.info(msg)
        await self.publish("Bifrost.Messsages.Info.SLE.CLTU", msg)
        try:
            self.cltu_object = CLTU()
            self.cltu_object.connect()
            await asyncio.sleep(5)

            self.cltu_object.bind()
            await asyncio.sleep(5)

            self.cltu_object.start(None, None)
            await asyncio.sleep(5)

            if self.cltu_object._state == 'active':
                msg = f"New Connection: CLTU interface is {self.cltu_object._state}!"
                log.info(msg)
                await self.publish("Bifrost.Messsages.Info.SLE.CLTU", msg)
            else:
                msg = "CLTU Interface encountered an error during startup."
                log.error(msg)
                await self.publish("Bifrost.Messsages.Error.SLE.CLTU", msg)
                
        except Exception as e:
            msg = f"CLTU SLE Interface Encountered exception {e}."
            log.error(msg)
            await self.publish("Bifrost.Messsages.Error.SLE.CLTU", msg)

    @with_loud_coroutine_exception
    async def handle_restart(self):
        await self.sle_stop()
        await self.connect()

    @with_loud_coroutine_exception
    async def sle_stop(self):
        if self.cltu_object:
            self.cltu_object.shutdown()
            await asyncio.sleep(self.restart_delay_s)

    @with_loud_coroutine_exception
    async def monitor(self):
        msg = {'state': None,
               'total_received': None}
        while True:
            await asyncio.sleep(self.report_time_s)
            msg['total_received'] = self.send_counter
            if self.cltu_object:
                msg['state']: self.cltu_object._state
            await self.publish('Bifrost.Monitors.SLE.CLTU', msg)
            log.debug(f"{msg}")

    @with_loud_coroutine_exception
    async def supervisor(self):
        if self.autorestart:
            log.info("Initial start of CLTU interface")
            await self.publish("Bifrost.Messages.Info.SLE.CLTU", 'Starting interface.')
            await self.handle_restart()
        while True:
            await asyncio.sleep(self.report_time_s)
            if self.cltu_object and self.cltu_object._state == 'active':
                log.debug("SLE OK!")
            elif not self.autorestart:
                await self.publish("Bifrost.Messages.Warn.SLE.CLTU", 'We got disconnected and autorestart is disabled. Send manual restart.')
                continue
            else:
                msg = ("Response not received from CLTU SLE responder "
                       "during bind request. Bind unsuccessful")
                await self.publish("Bifrost.Messages.Error.SLE.CLTU", msg)
                log.error(msg)
                await self.handle_restart()

    @with_loud_coroutine_exception
    async def uplink(self, topic, message, reply):
        try:
            self.cltu_object.upload_cltu(bytearray.fromhex(message['payload_bytes']))
            self.send_counter += 1
            ait.core.log.debug("uploaded CLTU")
            if message.get('data_type') == 'CmdMetaData':
                await self.stream('Uplink.CmdMetaData.Complete', message)

        except Exception as e:
            log.error(f"Encountered exception {e}.")
            await self.handle_restart()
