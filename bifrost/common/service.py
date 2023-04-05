from bifrost.common.loud_exception import with_loud_exception
from abc import abstractmethod
from ait.core import log
import pickle
import setproctitle
from colorama import Fore
import signal
import os

import asyncio
import nats
from nats.errors import ConnectionClosedError, TimeoutError, NoServersError, UnexpectedEOF
import traceback
import uvloop


class Service():
    def __init__(self):
        # Pro Tip: If you make an await call and nothing happens, try self.loop.create_task(f) and look for an exception
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        self.name = self.__class__.__name__
        setproctitle.setproctitle(self.name)

        self.reconfig_pattern = f'Bifrost.Plugins.Reconfigure.{self.__class__.__name__}'
        self.running = False

        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)

        self.loop = asyncio.get_event_loop()
        #try:
        self.loop.run_until_complete(self.nc_connect())
        #except Exception as e:
         #   print(e)

    async def handle_nats_error(self, e):
        if type(e) is UnexpectedEOF:
            log.error((f"{Fore.RED} If the NATS server is not dead, you most likely have a programming error: "
                       "You might have published the payload as the topic, which nats will truncate."
                       f"This causes the nats connection to die. {Fore.RESET}"))
            log.error(e)
        else:
            log.error(e)
        log.error(f"Killing {self}")
        os.kill(os.getpid(), signal.SIGKILL)
        raise e

    async def nc_connect(self):
        try:
            NATS_HOST = os.environ.get('NATS_HOST')
            if not NATS_HOST:
                NATS_HOST = 'localhost'
            self.nc = await nats.connect(f"nats://{NATS_HOST}:4222",
                                         name=f'Bifrost-{self.name}',
                                         error_cb=self.handle_nats_error)
            self.js = self.nc.jetstream()
            await self.subscribe_reconfigure()
        except Exception as e:
            print(f"Exception on nc connect! {e}")
            traceback.print_exc()
            log.error(e)
            exit()

    @with_loud_exception
    def start(self):
        try:
            setproctitle.setproctitle(f'Bifrost.{self.name}')
            self.running = True
            pending = asyncio.all_tasks(self.loop)
            self.loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except asyncio.exceptions.CancelledError:
            log.error(f"{self.name} => Cancelling tasks!")
            # Known issue is not quoting topic string in services.yaml
            os.kill(os.getpid(), signal.SIGTERM)
            exit()
        except Exception as e:
            log.error(e)
            traceback.print_exc()
            exit(-1)
                                                    
    def shutdown(self, signum, frame):
        self.running = False
        self.loop.create_task(self.nc.drain())
        pending = asyncio.all_tasks(self.loop)
        for i in pending:
            i.cancel()
        #print(f"{self.name} is receiveing sigkill.")
        os.system('pkill -9 Bifrost') # Work around to kill gunicorn task until supervisord implementation
        os.kill(os.getpid(), signal.SIGKILL)
        # And stay dead.
        
    @staticmethod
    def unpickled(f):
        async def _unpickled(msg):
            subject = msg.subject
            reply = msg.reply
            data = pickle.loads(msg.data)
            try:
                await f(subject, data, reply)
            except AttributeError as e:
                if "'coroutine' object has no attribute" in str(e):
                    log.error("You most likely have not called await on an async function and assigned the coroutine to a variable.")
                    traceback.print_exc()
                    os.kill(os.getpid(), signal.SIGTERM)
            except TypeError as e:
                if "can't be used in 'await' expression" in str(e):
                    log.error(f"{Fore.RED} You most likely called await on a non async function. {Fore.RESET}")
                    traceback.print_exc()
                    os.kill(os.getpid(), signal.SIGTERM)
            except nats.js.errors.NoStreamResponseError:
                log.error(f"{Fore.RED}You most likely did not declare the stream and subject for which you are atttempting to stream to, or forgot to await publish or stream.{Fore.RESET}")
                traceback.print_exc()
                os.kill(os.getpid(), signal.SIGTERM)
            except Exception as e:
                log.error(f"Could not execute {f} for message {subject=} {data=} {reply=}")
                log.error(e)
                traceback.print_exc()
                os.kill(os.getpid(), signal.SIGTERM)
        return _unpickled

    @with_loud_exception
    @abstractmethod
    async def reconfigure(self, topic, data, reply):
        async def make_subscription(t):
            if t == 'topics':
                subscribing_function = self.subscribe_topic
            elif t == 'streams':
                subscribing_function = self.subscribe_jetstream
            else:
                raise ValueError("Variable t must be  <'topics'|'streams'>")
            
            if not hasattr(self, t) or not (iterable := getattr(self, t)): # iterablle = self.topics or self.streams
                log.debug(f'No {t} found for {self}!')
                return

            for (function, t_list) in iterable.items():
                if not t_list:
                    log.debug(f"No {t} for {function} were specified.")
                    continue
                for i in t_list:
                    log.debug(f'Subscribing function -> {function} to {t} -> {i}') # log.info failing here?!
                    try:
                        f = getattr(self, str(function))
                    except AttributeError as e:
                        log.error(f"{e}")
                        continue
                    #await subscribing_function(i, f)
                    self.loop.create_task(subscribing_function(i, f))
                    
        def add_attributes():
            for (attribute, value) in data.items():
                if attribute in []:
                    log.info(f'{self}: Cannnot bind reserved attribute {attribute=} to {value=}')
                    continue
                setattr(self, attribute, value)

        async def unsubscribe():
            if hasattr(self, 'subscription'):
                await self.subscription.unsubscribe()
            if hasattr(self, 'subscription_stream'):
                await self.subscription_stream.unsubscribe()
        try:
            await unsubscribe()
            add_attributes()
            await make_subscription('topics')
            await make_subscription('streams')
            await self.subscribe_reconfigure()
        except Exception as e:
            log.error(e)
            raise e
        log.debug(f"{Fore.BLUE}Finished reconfiguration for {self.name} {Fore.RESET}")
        
    async def subscribe_reconfigure(self):
        await self.subscribe_topic(self.reconfig_pattern, self.reconfigure)

    async def subscribe_topic(self, topic, callback):
        f = self.unpickled(callback)
        self.subscription = await self.nc.subscribe(topic, cb=f)

    async def subscribe_jetstream(self, subject, callback):
        try:
            f = self.unpickled(callback)
            name = 'Bifrost-' + self.name.split('.')[-1]
            self.subscription_stream = await self.js.subscribe(subject=subject,
                                                               cb=f,
                                                               durable=name,
                                                               ordered_consumer=False,
                                                               flow_control=False)
        except TypeError as e:
            log.error(f"{Fore.RED} You most likely did not declare the stream or subject you are subscribing to.{Fore.RESET}")
            raise e
        except Exception as e:
            log.error(e)
            raise e
        
    async def stream(self, subject, data):
        if not data:
            log.error("No data?!")
            return
        data = pickle.dumps(data, pickle.HIGHEST_PROTOCOL)
        await self.js.publish(subject, data)

    async def publish(self, topic_pattern, data, reply=''):
        try:
            data = pickle.dumps(data, pickle.HIGHEST_PROTOCOL)
            await self.nc.publish(topic_pattern, data, reply)
            await self.nc.flush()
        except nats.errors.BadSubjectError:
            log.error(f'The pattern: "{topic_pattern}" is an invalid NATS subject')
        except TypeError as e:
            if 'pickle' in str(e):
                log.error(f"Could not pickle {data} for {topic_pattern}: {e}")

    async def request(self, subject, data=None):
        inbox = self.nc.new_inbox()
        sub = await self.nc.subscribe(inbox)
        await self.publish(subject, data, inbox)
        try:
            msg = await sub.next_msg(timeout=10)
            msg = pickle.loads(msg.data)
            return msg
        except nats.errors.TimeoutError:
            msg = f"No response from PUB/SUB network, or the service is taking longer than expected for call {subject} from {self.name}."
            log.error(msg)
            return msg
        except EOFError:
            log.error(f"Request on {subject} for {data} returned an empty reply.")
        except Exception as e:
            log.error(e)

    async def config_request(self, key_string):
        # TODO Explore using the NATS KV
        res = await self.request("Reconfiguration_Service.Request", key_string)
        return res

    async def config_request_pass_id(self):
        r = await self.config_request('global.mission.pass_id')
        return r

    def __del_(self):
        self.nc.close()

    def __repr__(self):
        return f"{self.name}"
