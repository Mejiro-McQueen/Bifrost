from bifrost.common.service import Service
from bifrost.common.loud_exception import with_loud_coroutine_exception, with_loud_exception
from ait.core import log
from ait.dsn.sle.raf import RAF
import asyncio

"""
A plugin which creates an RAF connection with the DSN.
Frames received via the RAF connection are sent to the output stream
"""


class SLE_RAF_Service(Service):
    @with_loud_exception
    def __init__(self):
        super().__init__()
        self.receive_counter = 0
        self.restart_delay_s = 5
        self.report_time_s = 5
        self.autorestart = False
        self.raf_object = None
        self.loop.create_task(self.monitor())
        self.loop.create_task(self.supervisor())
        self.start()

    @with_loud_coroutine_exception
    async def reconfigure(self, topic, message, reply):
        await super().reconfigure(topic, message, reply)
        self.output_queue = asyncio.Queue()
        asyncio.create_task(self.service_output_queue())
        return

    @with_loud_coroutine_exception
    async def directive_stop_sle(self, topic, message, reply):
        msg = "Received RAF Stop Directive!"
        log.info(msg)
        await self.publish("Bifrost.Messsages.Info.SLE.RAF", msg)
        await self.sle_stop()
        return

    @with_loud_coroutine_exception
    async def directive_restart_sle(self, topic, message, reply):
        msg = "Received RAF restart Directive!"
        log.info(msg)
        await self.publish("Bifrost.Messsages.Info.SLE.RAF", msg)
        await self.sle_stop()
        await asyncio.sleep(2)
        await self.handle_restart()

    @with_loud_coroutine_exception
    async def connect(self):
        msg = "Starting RAF interface."
        log.info(msg)
        await self.publish("Bifrost.Messsages.Info.SLE.RAF", msg)
        try:
            self.raf_object = RAF()
            self.raf_object._handlers['AnnotatedFrame'] = [self._transfer_data_invoc_handler]
            self.raf_object.connect()
            await asyncio.sleep(5)

            self.raf_object.bind()
            await asyncio.sleep(5)

            self.raf_object.start(None, None)
            await asyncio.sleep(5)

            if self.raf_object._state == 'active':
                msg = f"New Connection: RAF interface is {self.raf_object._state}!"
                log.info(msg)
                await self.publish("Bifrost.Messsages.Info.SLE.RAF", msg)
            else:
                msg = "RAF Interface encountered an error during startup."
                log.error(msg)
                await self.publish("Bifrost.Messsages.Error.SLE.RAF", msg)
                
        except Exception as e:
            msg = f"RAF SLE Interface Encountered exception {e}."
            log.error(msg)
            await self.publish("Bifrost.Messsages.Error.SLE.RAF", msg)

    @with_loud_coroutine_exception
    async def handle_restart(self):
        await self.sle_stop()
        await self.connect()

    @with_loud_coroutine_exception
    async def sle_stop(self):
        if self.raf_object:
            self.raf_object.shutdown()
            await asyncio.sleep(self.restart_delay_s)

    @with_loud_coroutine_exception
    async def service_output_queue(self):
        while True:
            tm_data = await self.output_queue.get()
            self.receive_counter += 1
            await self.stream(self.output_stream, tm_data)

    @with_loud_coroutine_exception
    async def monitor(self):
        msg = {'state': None,
               'total_received': None}
        while True:
            await asyncio.sleep(self.report_time_s)
            msg['total_received'] = self.receive_counter
            if self.raf_object:
                msg['state']: self.raf_object._state
            await self.publish('Bifrost.Monitors.SLE.RAF', msg)
            log.debug(f"{msg}")

    @with_loud_coroutine_exception
    async def supervisor(self):
        if self.autorestart:
            log.info("Initial start of RAF interface")
            await self.publish("Bifrost.Messages.Info.SLE.RAF", 'Starting interface.')
            await self.handle_restart()
        while True:
            await asyncio.sleep(self.report_time_s)
            if self.raf_object and self.raf_object._state == 'active':
                log.debug("SLE OK!")
            elif not self.autorestart:
                await self.publish("Bifrost.Messages.Warn.SLE.RAF", 'We got disconnected and autorestart is disabled. Send manual restart.')
                continue
            else:
                msg = ("Response not received from RAF SLE responder "
                       "during bind request. Bind unsuccessful")
                await self.publish("Bifrost.Messages.Error.SLE.RAF", msg)
                log.error(msg)
                await self.handle_restart()

    def _transfer_data_invoc_handler(self, pdu):
        """"""
        frame = pdu.getComponent()
        if "data" in frame and frame["data"].isValue:
            tm_data = frame["data"].asOctets()
        else:
            err = (
                "RafTransferBuffer received but data cannot be located. "
                "Skipping further processing of this PDU ..."
            )
            ait.core.log.info(err)
            return

        self.output_queue.put_nowait(tm_data)
