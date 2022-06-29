from enum import Enum, auto
class MessageType(Enum):
    """ 
    Corresponding to topics
    """
    REAL_TIME_TELEMETRY = auto()
    STORED_TELEMETRY = auto()
    VCID_COUNT = auto()
    LOG = auto()
