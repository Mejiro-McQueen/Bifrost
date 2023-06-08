from bifrost.common.service import Service
from bifrost.common.loud_exception import with_loud_exception, with_loud_coroutine_exception
from pathlib import Path
from ait.core import log
from bifrost.services.core.task_manager.task_types import Tasks, Task_Transformers
from collections import defaultdict
import boto3
import json
import errno
import asyncio
import traceback
from colorama import Fore
from bifrost.services.core.configuration import get_key_values


class Task_Manager(Service):
    @with_loud_exception
    def __init__(self):
        # Variables assigned in init are typically reserved through reconfiguration
        super().__init__()
        self.task_tracker = {}
        self.completed_file_reassembly = {"md5_pass": defaultdict(list),
                                          "md5_fail": defaultdict(list)}
        self.start()

    @with_loud_coroutine_exception
    async def reconfigure(self, topic, message, reply):
        # Let's use the nats connection while we still have it to get the new values
        # Get some global config values and create new local values based on them
        self.pass_id = await self.config_request_value("global.mission.pass_id")
        self.sv_name = await self.config_request_value('instance.space_vehicle.name')
        self.aws_region = await self.config_request_value('global.aws.region')
        self.aws_bucket = await self.config_request_value('global.aws.bucket')
        self.aws_profile = await self.config_request_value('global.aws.profile')

        # We can restart our connections and assign variables now.
        await super().reconfigure(topic, message, reply)

        self.use_s3 = self.auto_s3_upload and self.sv_name and self.aws_bucket and self.aws_region
        await self.initialize_s3()

    @with_loud_coroutine_exception
    async def finalize_s3(self, topic, task, reply):
        #log.info(f"Finalizing s3 upload {task=}")
        if not self.s3_resource:
            log.info(f"S3 Uploads are disabled! Skipping upload of {topic}")
            return
        await self.apply_transformers(task)
        task.execute(self.s3_resource)
        if not task.ID == -1:  # Do not track internal uploads
            await self.track_s3_upload(task)
        task.final = True

    @with_loud_coroutine_exception
    async def finalize(self, topic, task, reply):
        log.debug(f"Regular execution of {task}")
        task.execute()
        await self.apply_transformers(task)
        task.final = True

    @with_loud_coroutine_exception
    async def write_index(self, skip_s3=False):
        downlink_path = await self.request('Bifrost.Configuration.Downlink_Path')
        time_now = await self.request('Bifrost.Configuration.UTC_Now')
        index_filepath = Path(f'{downlink_path}/file_downlink/downlink_index_{self.sv_name}_{self.pass_id}.json')
        index_filepath.parent.mkdir(parents=True, exist_ok=True)
        a = {"session_time": time_now,
             'index': self.completed_file_reassembly,
             }
        await self.publish('Bifrost.Messages.Info.File_Manager.Reassembly_Report', a)
        try:
            with open(index_filepath, "w") as f:
                json.dump(a, f, indent=4)
                f.flush()

        except Exception as e:
            if e.errno == errno.ENOSPC:
                log.error("Out of disk space!")
            else:
                log.error(e)
            await self.publish('Bifrost.Messages.Errors.Panic.Write_Index', e)

        if skip_s3:
            return
        bytes_form = json.dumps(a).encode('ASCII')
        filename = index_filepath.name
        s3_path = f"data/{self.pass_id}/{self.sv_name}/file_downlink/{filename}"
        config = get_key_values()
        task = Tasks.S3_File_Upload(-1,
                                    self.aws_bucket,
                                    index_filepath,
                                    s3_path,
                                    self.aws_region,
                                    binary=bytes_form,
                                    pass_id=self.pass_id,
                                    sv_name=self.sv_name,
                                    config=config)
        task.nofork = True
        await self.publish(task.name, task)

    @with_loud_coroutine_exception
    async def initialize_s3(self):
        self.s3_resource = None
        if not self.use_s3:
            log.info("S3 connection disabled!")
            return
        log.info("Starting S3 connection")
        try:
            if self.aws_profile:
                self.session = boto3.Session(profile_name=self.aws_profile)
            else:
                self.session = boto3.Session()
            self.s3_resource = self.session.resource('s3')
            log.info("S3 connection successful")
        except Exception as e:
            log.error(f"S3 connection unsuccessful: {e}")

    @with_loud_coroutine_exception
    async def track_file_reassembly(self, completed_task):
        if completed_task.md5_file:
            self.completed_file_reassembly['md5_pass'][completed_task.ground_tag].append(completed_task.marshall(subset=True))
        else:
            self.completed_file_reassembly['md5_fail'][completed_task.ground_tag].append(completed_task.marshall(subset=True))
            await self.publish('Bifrost.Messages.Info.File_Manager.Retransmit_CL', str(completed_task.filepath))

        # Skip S3 upload if we can wait for the S3 file upload index update
        await self.write_index(not self.s3_resource)
        msg_type = "Bifrost.Messages.Info.File_Manager.File_Reassembly_Result"
        log.debug("Finalized file reassembly")
        await self.notify_pubsub(msg_type, completed_task)
        return

    @with_loud_coroutine_exception
    async def track_s3_upload(self, completed_task):
        if completed_task.filepath.suffix == '.cl':
            return
        if not completed_task.result:
            self.completed_file_reassembly['md5_pass'][completed_task.ground_tag][-1]['s3_metadata'] = completed_task.metadata
        await self.write_index()
        msg_type = "Bifrost.Messages.Info.File_Manager.S3_Upload"
        await self.notify_pubsub(msg_type, completed_task)
        return

    @with_loud_coroutine_exception
    async def finalize_reassembly(self, topic, task, reply):
        def get_bypass():
            bypass_file = Path(str(task['filepath']) + '.bypass')
            if bypass_file.exists():
                with open(bypass_file) as f:
                    return int(f.read())
            else:
                return 0

        def set_bypass(n):
            bypass_file = Path(str(task['filepath']) + '.bypass')
            with open(bypass_file, 'w') as f:
                f.write(str(n))

        if task['final']:
            return

        bypass = get_bypass()
        if bypass <= 0:
            if bypass < 0:
                set_bypass(0)
            log.info(f"Finalizing reassembly {task['filepath']}")
            task = getattr(eval(f"Tasks.{task['name']}"), "unmarshall")(task)
            task.execute()
            await self.track_file_reassembly(task)
            await self.apply_transformers(task)
        else:
            set_bypass(bypass - 1)
            log.info(f"Ground Tag: {task['ground_tag']} -> {task['filepath']} => Bypassing {bypass-1} more times.")
        task.final = True

    @with_loud_coroutine_exception
    async def apply_transformers(self, task):
        if task.final:
            return
        transformers = self.task_transformers.get(task.name, [])
        log.debug(f"Found transformers {task.name}  {transformers}")
        if not transformers:
            return
        for (transformer_name, options) in transformers.items():
            try:
                transformer = eval(f"Task_Transformers.{task.name}.{transformer_name}")
                log.debug(f"Transformer found: {transformer}")
                if options:
                    log.debug(f"with options: {options}")
                    new_task = transformer.transform(task,  **options)
                else:
                    log.debug("with no options")
                    new_task = transformer.transform(task)
                log.debug(f"Created new tasks: {new_task}")
                if new_task:
                    if isinstance(new_task, list):
                        for i in new_task:
                            await self.publish(i.name, i.marshall())
                    else:
                        await self.publish(new_task.name, new_task.marshall())
            except Exception as e:
                log.error(f"Could not apply transformer {transformer} on task {task.name}: {e}")
                raise e

    @with_loud_coroutine_exception
    async def notify_pubsub(self, msg_type, completed_task):
        if not msg_type:
            return
        msg = {}
        msg = {'task_id': completed_task.ID,
               'task_name': completed_task.name,
               'result': completed_task.marshall(subset=True),
               }
        await self.publish(msg_type, msg)


# TODO: This module is awful, should have written in in lisp
