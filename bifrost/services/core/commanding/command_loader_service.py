from bifrost.common.service import Service
from bifrost.common.loud_exception import with_loud_exception, with_loud_coroutine_exception
from pathlib import Path
from ait.core import log
import sunrise.packet_processors.scripts.sdlFts as sdlFts
from bifrost.services.core.commanding.cmd_meta_data import CmdMetaData
import tqdm
from colorama import Fore
import traceback
import asyncio

class CommandLoader():
    def __init__(self, request, publish, default_cl_path='',
                 default_uplink_path=''):
        self.request = request
        self.publish = publish
        self.uplink_trackers = {}
        self.default_cl_path = default_cl_path
        self.default_uplink_path = default_uplink_path

    @with_loud_coroutine_exception
    async def command_execute(self, cmd_struct: CmdMetaData, execute=True):
        args = cmd_struct.payload_string.split(" ")
        command = args.pop(0)
        cleaned_args = [str(i) for i in self.clean_args(args)]
        command = ' '.join([command, *cleaned_args])
        try:
            response = await self.request('Bifrost.Services.Command.Object',
                                          cmd_struct.payload_string)
            valid, obj = response
            if valid and execute:
                cmd_struct.payload_bytes = obj.encode()
                self.get_tracker(cmd_struct)
                await self.publish("Uplink.CmdMetaData", cmd_struct)
        except Exception as e:
            log.error(e)
            traceback.print_exc()
            valid = False
        return valid

    def get_tracker(self, cmd_struct):
        def new_tracker():
            pbar = tqdm.tqdm(total=cmd_struct.total, unit='commands', unit_scale=True, colour='BLUE', initial=0)
            pbar.set_description(f"{cmd_struct.payload_string}")
            return pbar

        tracker = self.uplink_trackers.get(cmd_struct.uid, None)
        if not tracker:
            tracker = new_tracker()
            self.uplink_trackers[cmd_struct.uid] = tracker
        return tracker

    def update_tracker(self, cmd_struct):
        tracker = self.get_tracker(cmd_struct)
        tracker.update()
        if tracker.n == tracker.total:
            tracker.close()
            log.info(f"Finished {cmd_struct.uid}")

    def close_tracker(self, cmd_struct):
        tracker = self.get_tracker(cmd_struct)
        tracker.close()

    @with_loud_coroutine_exception
    async def upload_dir(self, path, uid):
        # SunRISE Special
        p = Path(path)
        if not list(p.glob("*uplink_metadata.json")):
            return {'valid': False}
        log.info(f"Uploading {p}")
        try:
            metadata = sdlFts.send_uplink_products_from_directory(p, uid)
            for cmd_struct in metadata:
                self.get_tracker(cmd_struct)
                await self.publish('Uplink.CmdMetaData', cmd_struct)
            res = {'valid': True,
                   'uid': uid,
                   'execution_result': metadata[0].payload_string}
        except Exception as e:
            res = {'valid': False}
            log.error(e)
            traceback.print_exc()
        return res

    @with_loud_coroutine_exception
    async def validate(self, i):
        """Use Heuristics to perform validate"""
        res = {'valid': None}
        res = self.timestamp(res, 'start')
        path = Path(i)
        if path.is_dir():
            # SunRISE Special
            if list(path.glob("*uplink_metadata.json")):
                res['valid'] = True
            else:
                res['valid'] = False
        elif path.is_file():
            if path.suffix == ".cl":
                res['result'] = await self.cl_validate(path)
                res['valid'] = all(i['valid'] for i in res['result'])
            else:
                res['valid'] = False
        elif "/" in str(path):
            # Path like, but not on FS
            res['valid'] = False
        else:
            cmd_struct = CmdMetaData(i)
            res['valid'] = await self.command_execute(cmd_struct, execute=False)
        res = self.timestamp(res, 'finish')
        return res

    def clean_args(self, args):
        cleaned = []
        for i in args:
            # Try numeral, or default to string
            try:
                if '.' in i:
                    cleaned.append(float(i))
                else:  # Int or hex -> Int
                    cleaned.append(int(i, 0))
            except Exception:
                # Might be a string
                cleaned.append(i)
        return cleaned

    @with_loud_coroutine_exception
    async def execute(self, directive):
        """ Use Heuristics to determine what kind of execution to use"""
        uid = CmdMetaData.get_uid()
        res = {'result': None,
               'uid': str(uid)}
        res = self.timestamp(res, 'start')
        path = Path(directive)
        if path.is_dir():
            # uplink directory
            if list(path.glob("*uplink_metadata.json")):
                log.debug("SUNRISE: Upload Directory")
                uid = CmdMetaData.get_uid()
                upload = asyncio.create_task(self.upload_dir(directive, uid))
                res['result'] = 'Upload Task Started'
                res['valid'] = True
            else:
                res['result'] = False
                res['valid'] = False
        elif path.suffix == ".cl":
            # command loader script
            log.debug("Execute CL script")
            asyncio.create_task(self.execute_cl_script(path, uid))
            res['result'] = 'Accepted'
            res['valid'] = 'Maybe'
        #elif path.suffix == ".py":
            # TODO Do we need args?
            #log.info(f"Execute python script")
        #    result = self.execute_python(path)
        elif "/" in str(path):
            # Path like, but not on FS
            res['valid'] = False
            res['result'] = "Link not found"
        else:
            # raw command
            log.debug("Execute raw command")
            cmd_struct = CmdMetaData(directive)
            res['result'] = {'uid': str(cmd_struct.uid),
                             'valid': await self.command_execute(cmd_struct),
                             }
        res = self.timestamp(res, 'finish')
        return res

    @with_loud_coroutine_exception
    async def execute_cl_script(self, path, uid):
        log.info(f"Executing CL Script {path}")
        res = []
        commands = []
        with open(path, 'r') as f:
            cmd_strings = f.readlines()
        cmd_list = list(self.clean(cmd_strings))
        if not cmd_list:
            msg = f"{path=} is empty!"
            log.info(msg)
            return [{'command': '',
                     'valid': False}]
        for i in cmd_list:
            p = Path(i)
            if 'sleep' in i:
                # Change to regex at some point
                _, t = i.split(' ')
                res.append({'command': i,
                            'valid': True})
                commands.append((i, lambda: asyncio.sleep(float(t))))
            elif 'echo' in i:
                _, msg = i.split(' ')
                res.append({'command': i,
                            'valid': True})
                commands.append((i, lambda: log.info(msg)))
            elif p.is_dir():
                if list(p.glob("*uplink_metadata.json")):
                    log.info("SUNRISE: Upload Directory!")
                    result = 'Upload Task Started'
                    valid = True
                    commands.append(('FILE_UPLINK',
                                     lambda: self.upload_dir(p, uid)))
                else:
                    result = 'Invalid Uplink'
                    valid = False
                m = {'command': p,
                     'valid': valid,
                     'result': result}
                if valid:
                    m['uid'] = str(uid)
                res.append(m)
            else:
                commands.append((i, CmdMetaData(i)))

        uid = CmdMetaData.get_uid()
        l = len([i for i in commands if not callable(i[1])])
        i = 0
        for (string, c) in commands:
            if isinstance(c, CmdMetaData):
                i += 1
                c.uid = str(uid)
                c.total = l
                c.sequence = i
                res.append({'command': c.payload_string,
                            'valid': await self.command_execute(c),
                            'uid': c.uid})
            elif callable(c):
                if string == 'FILE_UPLINK':
                    asyncio.create_task(c)
                else:
                    r = await c()
                    if not r:
                        r = {'command': string,
                             'valid': False,
                             'uid': uid}
                    else:
                        r = {**r, **{'command': string}}
                    print(r)
                    res.append(r)
        #log.info(f"Execute {path}: Done.")
        return res

    def clean(self, lines):
        def is_comment(line):
            return not line or line[0] == "#"
        res = [i.strip() for i in lines]
        commands = filter(lambda a: (not is_comment(a)), res)
        return commands

    @with_loud_coroutine_exception
    async def cl_validate(self, path):
        log.info(f"Commencing CL Validate")
        result = []
        with open(path, 'r') as f:
            cmd_strings = f.readlines()
        cmd_list = self.clean(cmd_strings)
        for i in cmd_list:
            if 'sleep' in i:
                # Change to regex at some point
                result.append({'command': i,
                               'valid': True})
            else:
                res = await self.validate(i)
                res = res['valid']
                result.append({'command': i,
                               'valid': res})
        return result

    def show(self, path):
        def ls(path):
            files = []
            if path.exists() and path.is_dir():
                try:
                    uplinks = [str(i) for i in path.iterdir() if i.is_dir() or
                               i.suffix in ['.cl', '.py', '.bypass', '.md5', '.json', '.ndjson']]
                except PermissionError:
                    uplinks = []
                files += uplinks
            return files
    
        res = {'result': None}
        res = self.timestamp(res, 'start')
        if path:
            path = Path(path)
        else:
            path = Path('/')
        if path.is_dir():
            result = ls(path)
        elif path.is_file():
            with open(path, 'r') as f:
                result = f.readlines()
        else:
            result = None
        res = self.timestamp(res, 'finish')
        res['result'] = result
        return res

    def timestamp(self, res, kind):
        # kind = < start' | finish' >
        kind += '_time_gps'
        t = CmdMetaData.gps_timestamp_now()
        t.format = 'iso'
        res[kind] = str(t)
        return res
    
       
class Command_Loader_Service(Service):
    """
    Calls processor object and publish its publishables.
    """
    def __init__(self):
        super().__init__()
        self.command_loader = CommandLoader(self.request, self.publish)
        self.start()

    @with_loud_coroutine_exception
    async def execute(self, topic, msg, reply):
        log.info("Execute")
        res = await self.command_loader.execute(msg)
        res['directive'] = topic
        res['args'] = msg
        #log.info(f"Completed Commands: {res}")
        await self.publish(reply, res)

    @with_loud_coroutine_exception
    async def show(self, topic, msg, reply):
        log.info("Show")
        res = self.command_loader.show(msg)
        res['directive'] = topic
        res['args'] = msg
        #log.info(f"Completed Commands: {res}")
        await self.publish(reply, res)

    @with_loud_coroutine_exception
    async def validate(self, topic, msg, reply):
        log.info("Validate")
        res = await self.command_loader.validate(msg)
        res['directive'] = topic
        res['args'] = msg
        await self.publish(reply, res)

    @with_loud_coroutine_exception
    async def uplink_complete(self, topic, msg, reply):
        msg.set_finish_time_gps()
        self.command_loader.update_tracker(msg)
        await self.publish("Bifrost.Messages.Info.CommandLoader.Uplink_Status", msg.subset_map())
        await self.publish('Uplink.CmdMetaData.Log', msg)

    @with_loud_coroutine_exception
    async def reconfigure(self, topic, message, reply):
        await super().reconfigure(topic, message, reply)
        return
