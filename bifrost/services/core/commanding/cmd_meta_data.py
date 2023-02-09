from dataclasses import dataclass, field
import uuid
from astropy.time import Time

@dataclass
class CmdMetaData():
    payload_string: str = None
    payload_bytes: bytes = None
    sequence: int = 1
    total: int = 1
    arg_valid: bool = True
    payload_size_valid: bool = True
    frame_size_valid: bool = True
    vcid: int = 0
    mapid: int = 0
    priority: int = 0
    uid: str = field(default_factory=uuid.uuid4)
    uplink_id: int = None
    processors: list = field(default_factory=list)
    start_time_gps = None
    finish_time_gps = None

    def __post_init__(self):
        self.start_time_gps = self.gps_timestamp_now()
    
    @staticmethod
    def get_uid():
        return uuid.uuid4()

    def set_finish_time_gps(self):
        if not self.finish_time_gps:
            self.finish_time_gps = self.gps_timestamp_now()
        return self.finish_time_gps

    @staticmethod
    def gps_timestamp_now():
        return Time(Time.now(), format='gps', scale='tai', precision=9)
    
    def subset_map(self):
        res = {}
        self.start_time_gps.format = 'iso'
        self.finish_time_gps.format = 'iso'
        res['payload_string'] = self.payload_string
        res['uid'] = str(self.uid)
        #res['payload_bytes'] = str(self.payload_bytes)
        res['vcid'] = self.vcid
        res['mapid'] = self.mapid
        res['priority'] = self.priority
        res['frame_size_valid'] = self.frame_size_valid
        res['sequence'] = self.sequence
        res['total'] = self.total
        res['arg_valid'] = self.arg_valid
        #res['processors'] = str(self.processors)
        res['start_time_gps'] = str(self.start_time_gps)
        res['finish_time_gps'] = str(self.finish_time_gps)
        res['uplink_id'] = self.uplink_id
        return res
