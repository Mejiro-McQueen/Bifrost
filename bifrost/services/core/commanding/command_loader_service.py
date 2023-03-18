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
from enum import Enum, auto
import json

class Command_Type(Enum):
    FILE_UPLINK = auto()
    COMMAND = auto()
    CL = auto()
    INVALID = auto()
    SLEEP = auto()
    ECHO = auto()


def command_type_hueristic(i):
    path = Path(i)
    if path.is_dir() and list(path.glob("*uplink_metadata.json")):
        res = Command_Type.FILE_UPLINK
    elif path.is_file() and path.suffix in ['.cl']:
        res = Command_Type.CL
    elif "/" in str(path):
        res = Command_Type.INVALID
    elif 'echo' in i:
        res = Command_Type.ECHO
    elif 'sleep' in i:
        res = Command_Type.SLEEP
    else: #  We can probably just ask the dictionaries if the mnemonic is in the able
        res = Command_Type.COMMAND
    log.debug(res)
    return res


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
                #self.update_tracker(cmd_struct)
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
    async def upload_dir(self, path):
        # SunRISE Special
        p = Path(path)
        if not list(p.glob("*uplink_metadata.json")):
            return {'valid': False}
        log.info(f"Uploading {p}")
        uid = CmdMetaData.get_uid() # Huge sequences, so get a new uid
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
        command_type = command_type_hueristic(i)
        res = {'valid': False}
        res = self.timestamp(res, 'start')
        if command_type is Command_Type.FILE_UPLINK:
            res['valid'] = True
        elif command_type is Command_Type.CL:
            res['result'] = await self.cl_validate(Path(i))
            res['valid'] = all(i['valid'] for i in res['result'])
        elif command_type is Command_Type.COMMAND:
            cmd_struct = CmdMetaData(i)
            res['valid'] = await self.command_execute(cmd_struct, execute=False)
        elif command_type is Command_Type.ECHO:
            res['valid'] = True
        elif command_type is Command_Type.SLEEP:
            _, t = i.split(' ')
            res['valid'] = t.isnumeric()
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
    async def execute(self, directive, cmd_struct=None):
        """ Use Heuristics to determine what kind of execution to use"""
        if cmd_struct:
            uid = cmd_struct.uid
        else:
            uid = CmdMetaData.get_uid()
            
        res = {'result': None,
               'uid': str(uid)}
        res = self.timestamp(res, 'start')
        res['result'] = False
        res['valid'] = False
        
        command_type = command_type_hueristic(directive)
            # uplink directory
        if command_type is Command_Type.FILE_UPLINK:
            upload = asyncio.create_task(self.upload_dir(directive))
            res['result'] = 'Upload Task Started'
            res['valid'] = True
        elif command_type is Command_Type.CL:
            # command loader script
            log.debug("Execute CL script")
            asyncio.create_task(self.execute_cl_script(Path(directive), uid))
            res['result'] = 'Accepted'
            res['valid'] = 'Maybe'
        elif command_type is Command_Type.COMMAND:
            # raw command
            log.debug("Execute raw command")
            if not cmd_struct:
                cmd_struct = CmdMetaData(directive)
            res['result'] = {'uid': str(cmd_struct.uid),
                             'valid': await self.command_execute(cmd_struct)}
        elif Command_Type is Command_Type.INVALID:
            res['valid'] = False
            res['result'] = "Invalid Command"
        elif command_type is Command_Type.SLEEP:
            _, t = directive.split(' ')
            await asyncio.sleep(float(t))
        elif command_type is Command_Type.ECHO:
            log.info(directive)
            res['valid'] = True
            res['result'] = directive
        res = self.timestamp(res, 'finish')
        return res

    @with_loud_coroutine_exception
    async def execute_cl_script(self, path, uid):
        log.info(f"Executing CL Script {path}")
        with open(path, 'r') as f:
            cmd_strings = f.readlines()
        cmd_list = list(self.clean(cmd_strings))
        if not cmd_list:
            msg = f"{path=} is empty!"
            log.info(msg)
            return [{'command': '',
                     'valid': False}]
        res = []
        sequence = 0
        p = len([i for i in cmd_list if command_type_hueristic(i) is Command_Type.COMMAND])
        for i in cmd_list:
            cmd_struct = CmdMetaData(i)
            cmd_struct.total = p
            cmd_struct.uid = uid
            a = await self.execute(i, cmd_struct)
            sequence += 1
            cmd_struct.sequence = sequence
            res.append(a)
            #print(Fore.CYAN, cmd_struct, Fore.RESET)
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
            a = await self.validate(i)
            m = {'command': i, **a}
            result.append(m)
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
