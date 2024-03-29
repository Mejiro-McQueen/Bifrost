from bifrost.common.service import Service
from bifrost.common.loud_exception import with_loud_exception, with_loud_coroutine_exception
from pathlib import Path
from ait.core import log

from bifrost.services.core.commanding.cmd_meta_data import CmdMetaData
import tqdm
from colorama import Fore
import traceback
import asyncio
from enum import Enum, auto
import ast


class Command_Type(Enum):
    FILE_UPLINK = auto()
    COMMAND = auto()
    CL = auto()
    INVALID = auto()
    SLEEP = auto()
    ECHO = auto()


def command_type_hueristic(i):
    path = Path(i)
    try:
        is_dir = path.is_dir()
        is_file = path.is_file()
    except Exception:
        is_dir = False
        is_file = False
    if is_dir and list(path.glob("*uplink_metadata.json")):
        res = Command_Type.FILE_UPLINK
    elif is_file and path.suffix == '.cl':
        res = Command_Type.CL
    elif "/" in str(path):
        res = Command_Type.INVALID
    elif 'echo' in i:
        res = Command_Type.ECHO
    elif 'sleep' in i:
        res = Command_Type.SLEEP
    else:  #  We can probably just ask the dictionaries if the mnemonic is in the dict
        res = Command_Type.COMMAND
    log.debug(res)
    return res


class CommandLoader():
    @with_loud_exception
    def __init__(self, request, publish, stream, default_cl_path='',
                 default_uplink_path=''):
        self.request = request
        self.publish = publish
        self.stream = stream
        self.uplink_trackers = {}
        self.default_cl_path = default_cl_path
        self.default_uplink_path = default_uplink_path

    @with_loud_coroutine_exception
    async def dispatch_command(self, cmd, uid, sequence, total, dry_run=False):
        args = cmd.split(" ")
        command = args.pop(0)
        cleaned_args = [str(i) for i in self.clean_args(args)] # TODO: clean args be doing the splits and pops?
        command = ' '.join([command, *cleaned_args])
        try:
            cmd_struct = await self.request('Bifrost.Services.Dictionary.Command.Generate', command)
            cmd_struct['uid'] = uid
            cmd_struct['sequence'] = sequence
            cmd_struct['total'] = total
            if cmd_struct['valid'] and not dry_run:
                await self.stream("Uplink.CmdMetaData", cmd_struct)
        except Exception as e:
            log.error(e)
            traceback.print_exc()
            cmd_struct = None
        return cmd_struct

    def get_tracker(self, cmd_struct):
        def new_tracker():
            pbar = tqdm.tqdm(total=cmd_struct['total'], unit=' commands', colour='BLUE', initial=cmd_struct['sequence'])
            pbar.set_description(f"Command Loader: {cmd_struct['payload_string']}")
            return pbar
        tracker = self.uplink_trackers.get(cmd_struct['uid'], None)
        if not tracker:
            tracker = new_tracker()
            self.uplink_trackers[cmd_struct['uid']] = tracker
        return tracker

    def update_tracker(self, cmd_struct):
        tracker = self.get_tracker(cmd_struct)
        tracker.update()
        if tracker.n == tracker.total:
            tracker.close()
            log.info(f"Finished {cmd_struct['uid']}")

    def close_tracker(self, cmd_struct):
        tracker = self.get_tracker(cmd_struct)
        tracker.close()

    @with_loud_coroutine_exception
    async def upload_dir(self, path):
        # TODO: Let file uplink services handle the heuristics, since it can be a special snowflake
        pass
    
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
            cmd_struct = await self.request('Bifrost.Services.Dictionary.Command.Validate', i)
            if cmd_struct is not None:
                res['valid'] = cmd_struct['valid']
            else:
                res['valid'] = False
            res['payload'] = cmd_struct['payload_bytes']
            res['command'] = cmd_struct['payload_string']
            if res['payload']:
                res['payload'] = "Redacted" #res['payload']
            else:
                res['payload'] = 'Error'
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
    async def execute(self, directive, uid=None, sequence=1, total=1):
        """ Use Heuristics to determine what kind of execution to use"""
        if not uid:
            uid = CmdMetaData.get_uid()
            
        res = {'result': None,
               'uid': uid}
        res = self.timestamp(res, 'start')
        res['result'] = False
        res['valid'] = False
        
        command_type = command_type_hueristic(directive)
            # uplink directory
        if command_type is Command_Type.FILE_UPLINK:
            #uid = CmdMetaData.get_uid()
            directive = {
                'uid': uid,
                'path': directive
            }
            valid = await self.request("Bifrost.Uplink.File", directive)
            res['result'] = {'uid': uid,
                             'valid': valid}
            if valid:
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
            cmd_struct = await self.dispatch_command(directive, uid, sequence, total)
            res['result'] = {'uid': cmd_struct['uid'],
                             'valid': cmd_struct['valid']}
            
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
        sequence = 1
        res = []
        uid = CmdMetaData.get_uid()
        total = len([i for i in cmd_list if command_type_hueristic(i) is Command_Type.COMMAND])
        for i in cmd_list:
            a = await self.execute(i, uid, sequence, total)
            sequence += 1
            res.append(a)
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
        res[kind] = t
        return res
    
       
class Command_Loader_Service(Service):
    """
    Calls processor object and publish its publishables.
    """
    def __init__(self):
        super().__init__()
        self.command_loader = CommandLoader(self.request, self.publish, self.stream)
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
        msg['finish_time_gps'] = CmdMetaData.gps_timestamp_now()
        self.command_loader.update_tracker(msg)
        await self.publish("Bifrost.Messages.Info.CommandLoader.Uplink_Status", msg)
        await self.publish('Uplink.CmdMetaData.Log', msg)
        #log.info(msg)

    @with_loud_coroutine_exception
    async def reconfigure(self, topic, message, reply):
        await super().reconfigure(topic, message, reply)
        return


# TODO: Might as well include encoded payload in receipt on execute?
