from bifrost.common.service import Service
from bifrost.common.loud_exception import with_loud_exception, with_loud_coroutine_exception
from bifrost.common.deep_dictionary_get import deep_get
import bifrost.services.core.configuration as cfg

from pathlib import Path
import inotify.adapters
import asyncio
from ait.core import log
from collections import defaultdict
import traceback
from colorama import Fore
from datetime import datetime


class Configuration(Service):
    # TODO at some point we would want to just push keys onto jetstream
    # However, this pythonlib is experimental and we can't actually watch the key
    @with_loud_exception
    def __init__(self):
        self.watchdog_timer_s = 1
        super().__init__()
        self.loop.create_task(self.add_streams())
        self.loop.create_task(self.watch_reconfig())
        self.reconfiguration_maps = defaultdict(dict)
        self.config_path = cfg.get_config_path()
        self.service_map = cfg.get_services()
        self.start()

    @with_loud_coroutine_exception
    async def utc_timestamp_now(self, topic, data, reply):
        await self.publish(reply, datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S"))

    @with_loud_coroutine_exception
    async def request_downlink_path(self, topic, data, reply):
        await self.publish(reply, self.downlink_path)

    @with_loud_coroutine_exception
    async def add_streams(self):
        """Before we do _anything_ else, we need to make sure the NATS Jetstreams are created."""
        try:
            cname = str(type(self)).split("'")[1]
            metadata = cfg.get_services()[cname]
            stream_declarations = metadata['stream_declarations']
            for (stream, subjects) in stream_declarations.items():
                #print(stream, subjects)
                await self.js.add_stream(name=stream, subjects=subjects)
            await asyncio.sleep(3)
        except Exception as e:
            traceback.print_exc()
            log.error(e)

    @with_loud_coroutine_exception
    async def request_config_value(self, topic, data, reply):
        if not data:
            await self.publish(reply, self.key_values)
        res = deep_get(self.key_values, data)
        await self.publish(reply, res)

    @with_loud_coroutine_exception
    async def watch_reconfig(self):
        async def emit_reconfigure():
            for (plugin_class, metadata) in self.service_map.items():
                class_name = str(Path(plugin_class).suffix[1:])
                if not self.reconfiguration_maps[class_name] == metadata:
                    log.info(f'{Fore.CYAN}config.yaml modified: emitting reconfig on {class_name} {Fore.RESET}')
                    await self.publish(f'Bifrost.Plugins.Reconfigure.{class_name}',
                                       metadata)
                    self.reconfiguration_maps[class_name] = metadata
                    #print(Fore.RED, "WE HAVE DIFF!", Fore.RESET)
                    #log.info(f'{Fore.CYAN} {plugin_class=} {metadata} {Fore.RESET}')
                
        file_observer = inotify.adapters.Inotify()
        file_observer.add_watch(str(self.config_path))
        print(self.config_path)
        await asyncio.sleep(self.watchdog_timer_s)
        await emit_reconfigure()
        while self.running:
            #emit_reconfigure()
            events = []
            events = file_observer.event_gen(timeout_s=1)
            events = list(events)
            for event in events:
                if not event:
                    break
                (_, type_names, path, filename) = event
                if type_names == ['IN_MODIFY']:
                    self.service_map = cfg.get_services()
                    await emit_reconfigure()
                    break
            await asyncio.sleep(self.watchdog_timer_s)

    @with_loud_coroutine_exception
    async def reconfigure(self, topic, data, reply):
        await super().reconfigure(topic, data, reply)
        self.config_path = cfg.get_config_path()
        self.service_map = cfg.get_services()
        self.startup_time = self.utc_timestamp_now()
        self.pass_id = deep_get(self.key_values, 'global.mission.pass_id')
        self.data_path = Path(deep_get(self.key_values, 'global.paths.data_path'))
        self.sv_name = deep_get(self.key_values, 'instance.space_vehicle.sv_name')
        assert self.pass_id is not None
        assert self.sv_name
        assert self.data_path
        self.downlink_path = Path(self.data_path / str(self.pass_id) / str(self.sv_name) / 'downlink')
        self.downlink_path.mkdir(parents=True, exist_ok=True)
