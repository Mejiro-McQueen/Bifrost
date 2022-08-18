from enum import Enum
from ait.core import log
from pathlib import Path
import tarfile
import bz2
from abc import ABC, abstractmethod

class MessageType(Enum):
    """
    Use these types to annotate pub sub messages for modules that:
      1. Publishes multiple types of data.
      2. The published data is passed to an external application (openmctvia websocket).
      3. A non plugin module is borrowing a plugin's publish function, making it not obvious that PUB/SUB messages are being emitted. (See RAF SLE interface for example).

    It's not necessary to use these types for inter plugin communication. Continue to use plugin names or strings to explicitly chain plugins together into a pipeline.

    USAGE:
        Send a message:
          self.publish(packet_metadata_list, MessageType.VCID_COUNT.name)
    """
    REAL_TIME_TELEMETRY = "realtime telemetry packets and metadata"
    STORED_TELEMETRY = "stored telemetry packets and metadata"
    VCID_COUNT = "vcid counts"
    LOG = "messages from log stream"
    CLTU_STATUS = "CLTU interface: <ACTIVE|READY|UNBOUND>,\n last status report,\n count of CLTU sent"
    RAF_DATA = "Raw telemetry from RAF Interface"
    RAF_STATUS = "RAF interface: <ACTIVE|READY|UNBOUND>,\n  last status report,\n count of data received"
    HIGH_PRIORITY_CLTU_STATUS = "High priority CLTU Interfce Status\n (Disconnect/Restarts)"
    HIGH_PRIORITY_RAF_STATUS = "High priority RAF Interfce Status\n (Disconnect/Restarts)"
    TCP_STATUS = "Number of packets transferred/received"
    KMC_STATUS = "If message is received\n, KMC Plugin is active"
    SC_STATE_OF_HEALTH_REPORT = "Spacecraft state of health report"
    GRAFFITI_MAP = "DOT file containing AIT Pipeline" # TODO Do we want this, and does Joe want a DOT or PNG?
    FILE_DOWNLINK_RESULT = "Result of a File Downlink Reassembly Task"
    FILE_DOWNLINK_UPDATE = "Result of a File Dowlink Update Task"
    TASK_S3_UPLOAD_RESULT = "Result of an S3 File Upload Task"
    PANIC = "Something has thrown an exception"
    CL_LIST = 'List command loader scripts, message is path or "" '
    CL_SHOW = 'Get contents of command loader script or uplink info, message is path to command loader script or uplink directory'
    CL_EXECUTE = 'Have command loader execute a command from the dicionary, message is a command or uplink directory'
    CL_VALIDATE = 'Have command loader verify a script, command, or uplink path'
    CL_RESULT = 'Contains result of Command Loader action {(action, argument): (BOOL, [Errors])}'
    FM_TASK_DONE = 'Generic task done for File Manager'
    FM_DL_STATUS = "Status of completed downlinks and S3 uploads"

    def to_tuple(self):
        return (self.name, self.value)


class Task_Message(ABC):

    @classmethod
    def name(cls):
        return cls.__name__

    def __init__(self, ID, filepath):
        self.ID = ID
        self.result = None # Result is usually published overpubsub
        self.name = self.name()
        self.filepath = Path(filepath)
        self.final = False # Task is final and can be ignored, use to prevent loop, see openmct usage

    def __repr__(self):
        return str(self.__dict__)

    @abstractmethod
    def execute(self):
        pass


class File_Reassembly_Task(Task_Message):
    """ This task is run automatically with ID = downlink ID"""
    def __init__(self, filepath, ground_id, SCID=0, file_reassembler=None):
        Task_Message.__init__(self, ground_id, filepath)
        self.filename = self.filepath.name
        self.ground_id = ground_id
        self.md5_pass = False
        self.SCID = SCID
        self.file_reassembler = file_reassembler

    def subset_map(self):
        a = {"status": self.result['initialize_file_downlink_reply']['status'],
             "md5_pass": self.md5_pass,
             "filepath": str(self.filepath.parent/self.filename)}
        return a

    def execute(self):
        self.file_reassembler(self.filepath.parent, None, self)


class S3_File_Upload_Task(Task_Message):
    """
    Request FileManager to upload local path to S3 bucket.
    If this task has ID 0, then it was run automatically by AIT from a File_Reassembly_Task.
    """
    def __init__(self, ID, bucket, filepath, s3_path, s3_region, ground_id):
        Task_Message.__init__(self, ID, filepath)
        self.bucket = bucket
        self.s3_path = s3_path
        self.ground_id = ground_id
        self.s3_region = s3_region

    def canonical_s3_url(self):
        if not self.result: # S3 upload returns none when successful, contains an exception otherwise
            a = f"https://{self.bucket}.s3-{self.s3_region}.amazonaws.com/{self.s3_path}"
            b = {'s3_url': a,
                 's3_region': self.s3_region,
                 's3_bucket': self.bucket,
                 's3_key': str(self.s3_path)}
            return b
        else:
            return None

    def execute(self, s3_resource):
        try:
            response = s3_resource.Bucket(self.bucket).upload_file(str(self.filepath), self.s3_path)
            if not response:
                self.result = True
        except Exception as e:
            log.error(e)
            self.result = str(e)
        log.info(f"Task ID {self.ID} -> {self.filepath} uploaded to {self.s3_path}")


class CSV_to_Influx_Task(Task_Message):
    def __init__(self, ID, filepath, postprocessor):
        Task_Message.__init__(self, ID, filepath)
        self.postprocessor = postprocessor
        self.measurement = None
        self.df = None

    def execute(self):
        self.measurement, self.df = self.postprocessor(self.filepath)
        self.result = True


class Tar_Decompress_Task(Task_Message):

    def __init__(self, ID, filepath):
        Task_Message.__init__(self, ID, filepath)
        self.result = None

    def decompress(self):
        with tarfile.open(self.filepath) as tar:
            try:
                tar.extractall(self.filepath.parent)
                self.result = self.filepath.parent
            except Exception as e:
                log.warn(f"Task ID: {self.ID} {self.filepath} could not be untarred: {e} ")

    def execute(self):
        self.decompress()


class Bz2_Decompress_Task(Task_Message):
    def __init__(self, ID, filepath):
        Task_Message.__init__(self, ID, filepath)

    def execute(self):
        self.decompress()
        return self.result

    def decompress(self):
        with bz2.open(self.filepath) as f:
            try:
                with open(self.filepath.with_suffix(''), 'wb') as g:
                    g.write(f.read())
                    self.result = self.filepath.with_suffix('')
            except Exception as e:
                log.warn(f"Task ID:{self.ID} {self.filepath} could not be decompressed: {e}")
