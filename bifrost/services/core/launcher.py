from bifrost.common.service import Service
from bifrost.common.loud_exception import with_loud_exception
import os
from pathlib import Path
from importlib import import_module
import concurrent.futures
import bifrost.services.core.configuration as cfg
from colorama import Fore
import traceback
from ait.core import log
from time import sleep

# TODO Look into https://github.com/Supervisor/supervisor
# This is bunk, let's make everything an executable


class Launcher(Service):
    """This service is bootstrapped by ./bifrost"""
    def __init__(self):
        super().__init__()
        self.process_map_to_pid = {'Launch_Service': os.getpid()}
        print(f"{Fore.GREEN}Bifrost Launch Service: Launch is starting.{Fore.RESET}")
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

    @with_loud_exception
    def start_process(self, service_metadata_dict):
        """Currently should only be run once"""
        max_workers = len([i for i in service_metadata_dict.values() if not i.get('disabled', False)])
        try:
            with concurrent.futures.ProcessPoolExecutor(max_workers) as executor:
                for (plugin_class, metadata) in service_metadata_dict.items():
                    class_name = Path(plugin_class).suffix[1:]
                    if metadata.get('disabled', False) is True:
                        print(f"{Fore.RED}Bifrost Launch Service: {class_name} is disabled.{Fore.RESET}")
                        continue
                    elif class_name in self.process_map_to_pid:
                        continue
                    else:
                        print(f"{Fore.GREEN}Bifrost Launch Service: {class_name} is starting.{Fore.RESET}")
                        try:
                            module_name = Path(plugin_class).stem
                            module = import_module(module_name, plugin_class)
                            class_type = getattr(module, class_name)
                            proc = executor.submit(Process, class_type)
                            self.process_map_to_pid[class_name] = proc
                        except Exception as e:
                            log.error(f"Error importing module named {plugin_class}")
                            log.error(e)
                            traceback.print_exc()
                            raise e
                # Now that services up, tell the Configuration service to emit
                t = 5
                log.info(f"Waiting for {t} seconds for coldstart.")
                sleep(t)
                self.loop.run_until_complete(self.publish('Bifrost.Configuration.Emit.All', ''))
                    
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
