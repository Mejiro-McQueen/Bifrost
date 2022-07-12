from enum import Enum
from dataclasses import dataclass

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
    TASK_S3_UPLOAD_RESULT = ""
    
class Task_Message():
    def __init__(self, _id, _metadata):
        self._id = _id
        self._metadata = _metadata
        self.result = None
        self.status = "pending"
        self.name = self.__class__.__name__

class File_Reassembly_Task(Task_Message):
    """ This task is run automatically with ID 0"""
    def __init__(self, _id, path):
        _metadata = {'path': path}
        _id = 0
        Task_Message.__init__(self, _id, _metadata)

class S3_File_Upload_Task(Task_Message):
    """
    Request FileManager to upload local path to S3 bucket.
    If this task has ID 0, then it was run automatically by AIT from a File_Reassembly_Task.
    """
    def __init__(self, _id, path, url):
        _metadata = {'url': str(url),
                     'path': path}
        Task_Message.__init__(self, _id, _metadata)
                
