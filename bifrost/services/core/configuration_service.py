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
        self.cmd_dict_path = cfg.get_cmd_dict_path()
        self.tlm_dict_path = cfg.get_tlm_dict_path()
        self.start()

    @with_loud_coroutine_exception
    async def utc_timestamp_now(self, topic, data, reply):
        ts = datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
        if reply:
            await self.publish(reply, ts)
        return ts

    @with_loud_coroutine_exception
    async def request_downlink_path(self, topic, data, reply):
        await self.publish(reply, str(self.downlink_path))

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
        file_observer.add_watch(str(self.cmd_dict_path))
        file_observer.add_watch(str(self.tlm_dict_path))
        #print(self.config_path)
        await asyncio.sleep(5) # TODO: Fix race condition, see notes.
        await emit_reconfigure()
        while self.running:
            #emit_reconfigure()
            events = []
            events = file_observer.event_gen(timeout_s=1)
            events = list(events)
            for event in events:
                if not event:
                    break
                (_, type_names, path, _) = event
                path = Path(path)
                if type_names == ['IN_MODIFY']:
                    if path == self.config_path:                    
                        self.service_map = cfg.get_services()
                        await emit_reconfigure()
                    
                    elif path == self.cmd_dict_path:
                        log.info(f'{Fore.CYAN}{path} modified: emitting reconfig on dictionary services {Fore.RESET}')
                        await self.publish('Bifrost.Plugins.Reconfigure.Command_Dictionary_Service', '')
                    
                    elif path == self.tlm_dict_path:
                        log.info(f'{Fore.CYAN}{path} modified: emitting reconfig on dictionary services {Fore.RESET}')
                        await self.publish('Bifrost.Plugins.Reconfigure.Telemetry_Dictionary_Service', '')
                    #log.error(event)
                    #log.error(f'{self.config_path}, {self.tlm_dict_path}, {self.cmd_dict_path}')
                    break
            await asyncio.sleep(self.watchdog_timer_s)

    @with_loud_coroutine_exception
    async def reconfigure(self, topic, data, reply):
        await super().reconfigure(topic, data, reply)
        self.config_path = cfg.get_config_path()
        self.service_map = cfg.get_services()
        self.startup_time = await self.utc_timestamp_now(None, None, None)
        self.pass_id = deep_get(self.key_values, 'global.mission.pass_id')
        self.data_path = Path(deep_get(self.key_values, 'global.paths.data_path'))
        self.sv_name = deep_get(self.key_values, 'instance.space_vehicle.sv_name')
        assert self.pass_id is not None
        assert self.sv_name
        assert self.data_path
        self.downlink_path = Path(self.data_path / str(self.pass_id) / str(self.sv_name) / 'downlink')
        self.downlink_path.mkdir(parents=True, exist_ok=True)
        self.cmd_dict_path = cfg.get_cmd_dict_path()
        self.tlm_dict_path = cfg.get_tlm_dict_path()
