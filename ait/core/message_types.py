from enum import Enum
from ait.core import log


class MessageType(Enum):
    """
    Use these enums (pubsub topics) when the type of data published is more important than the module who published it. (e.g, OpenMCT doesn't care who vcid_router plugin is, but it certainly cares about the VCID_COUNT it periodically publishes.)

    Q: Why not just pass a string to publish?
    A: Type Safety. Another developer can search for data they're interested in.

    Use these types to annotate pub sub messages for modules that:
      1. Publishes multiple types of data.
      2. The published data is passed to an external application.
      3. A non plugin module is borrowing a plugin's publish function, making it not obvious that PUB/SUB messages are being emitted. (See RAF SLE interface for example).

    It's not necessary to use these types for inter plugin communication. Continue to use plugin names or strings to explicitly chain plugins together into a pipeline.

    USAGE:
        Send a message:
          msg_type = MessageType.VCID_COUNT
          self.publish((msg_type, packet_metadata_list), msg_type.name)
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
    TASK_FILE_DOWNLINK_RESULT = "Result of a File Downlink Reassembly Task"
    TASK_FILE_DOWNLINK_UPDATE = "Result of a File Dowlink Update Task"
    TASK_S3_UPLOAD_RESULT = "Result of an S3 File Upload Task"

    def to_tuple(self):
        return (self.name, self.value)


class Task_Message():

    @classmethod
    def name(cls):
        return cls.__name__

    def __init__(self, ID):
        self.ID = ID
        self.result = None
        self.name = self.name()

    def __repr__(self):
        return str(self.__dict__)


class File_Reassembly_Task(Task_Message):
    """ This task is run automatically with ID 0"""
    def __init__(self, path, filename, ground_id):
        Task_Message.__init__(self, 0)
        self.path = path
        self.filename = filename
        self.ground_id = ground_id
        self.md5_pass = False

    def subset_map(self):
        a = {"status": self.result['initialize_file_downlink_reply']['status'],
             "md5_pass": self.md5_pass,
             "filepath": str(self.path/self.filename)}
        return a
        
class S3_File_Upload_Task(Task_Message):
    """
    Request FileManager to upload local path to S3 bucket.
    If this task has ID 0, then it was run automatically by AIT from a File_Reassembly_Task.
    """
    def __init__(self, ID, bucket, filepath, s3_path, s3_region, ground_id):
        Task_Message.__init__(self, ID)
        self.bucket = bucket
        self.filepath = filepath
        self.s3_path = s3_path
        self.ground_id = ground_id
        self.s3_region = s3_region
        
    def canonical_s3_url(self):
        if self.result: # A result implies an error occured
            return None
        a = f"https://{self.bucket}.s3-{self.s3_region}.amazonaws.com/{self.s3_path}"
        b = {'s3_url': a,
             's3_region': self.s3_region,
             's3_bucket': self.bucket,
             's3_key': str(self.s3_path)}
        return b


class CSV_to_Influx_Task(Task_Message):
    def __init__(self, ID, filepath, postprocessor):
        Task_Message.__init__(self, ID)
        self.filepath = filepath
        self.postprocessor = postprocessor
        self.measurement, self.df = self.postprocessor(filepath)


class Tar_Decompress_Task(Task_Message):
    from pathlib import Path
    import tarfile
    import bz2
    import io

    def __init__(self, ID, filepath, recursive=False):
        Task_Message.__init__(self, ID)
        self.filepath = self.Path(filepath)
        self.result = []
        self.process()

    def process(self):
        self.decompress(self.filepath)
        return self.result

    def decompress(self, filepath):
        with self.tarfile.open(filepath) as tar:
            tar.extractall(filepath.parent)

        for i in filepath.parent.glob('*.bz2'):
            with self.bz2.open(i) as f:
                with open(i.with_suffix(''), 'wb') as g:
                    g.write(f.read())
                    self.result.append(i.with_suffix(''))
