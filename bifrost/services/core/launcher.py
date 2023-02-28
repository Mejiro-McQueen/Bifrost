from bifrost.common.service import Service
import os
from pathlib import Path
from importlib import import_module
import concurrent.futures
import bifrost.services.core.configuration as cfg
from colorama import Fore
import traceback
from ait.core import log

# TODO Look into https://github.com/Supervisor/supervisor


class Launcher(Service):
    """This service is bootstrapped by ./bifrost"""
    def __init__(self):
        super().__init__()
        self.process_map_to_pid = {'Launch_Services': os.getpid()}        
        self.launch_all_services()
        self.start()

    async def reconfigure(self, topic, data, reply):
        await super().reconigure(topic, data, reply)

    async def launch_service(self, topic, data, reply):
        pass

    def launch_all_services(self):
        pm = cfg.get_services()
        #print(pm)
        self.start_process(pm)

    async def halt_service(self, topic, data, reply):
        pass

    def start_process(self, service_metadata_dict):
        """Currently should only be run once"""
        max_workers = len([i for i in service_metadata_dict.values() if not i.get('disabled', False)])
        try:
            with concurrent.futures.ProcessPoolExecutor(max_workers) as executor:
                for (plugin_class, metadata) in service_metadata_dict.items():
                    class_name = Path(plugin_class).suffix[1:]
                    if metadata.get('disabled', False):
                        print(f"{Fore.RED}Bifrost Launch Service: {class_name} is disabled.{Fore.RESET}")
                        continue
                    elif class_name in self.process_map_to_pid:
                        continue
                    else:
                        print(f"{Fore.GREEN}Bifrost Launch Service: Starting service {class_name} {Fore.RESET}")
                        try:
                            module = import_module(Path(plugin_class).stem)
                            class_type = getattr(module, class_name)
                            proc = executor.submit(Process, class_type)
                            self.process_map_to_pid[class_name] = proc
                        except Exception as e:
                            print(e)
                            traceback.print_exc()
                            raise e
                    
        except KeyboardInterrupt:
            executor.shutdown()
            log.info("ALL OK! Caught SIGTERM! Shutting down!")
        except Exception as e:
            print(e)
            executor.shutdown()
            traceback.print_exc()
            exit(-1)


class Process():
    """ Run python processes in here"""
    def __init__(self, class_type):
        try:
            class_type()
        except KeyboardInterrupt as e:
            print("Received SIGINT for {class_type}")
            exit()
        except Exception as e:
            log.error(f'Error intializing {class_type}')
            log.error(e)
            traceback.print_exc()
            exit()
