from bifrost.common.service import Service
from bifrost.common.loud_exception import with_loud_coroutine_exception, with_loud_exception
from colorama import Fore, Back, Style
from ait.core import log
import traceback
import json


class EVR_Service(Service):
    @with_loud_exception
    def __init__(self):
        super().__init__()
        self.start()

    @with_loud_coroutine_exception
    async def reconfigure(self, topic, message, reply):
        await super().reconfigure(topic, message, reply)
        return

    @with_loud_coroutine_exception
    async def process_evr(self, topic, message, reply):
        m = f"{Back.CYAN}{Fore.BLACK} EVR: " + json.dumps(message, indent=4) + Style.RESET_ALL
        log.info(m)
        await self.publish('Bifrost.Messages.EVR', message)
        return message
