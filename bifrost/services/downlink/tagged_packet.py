from dataclasses import dataclass, field
from datetime import datetime
import astropy.time
import ait

pass_number = str(ait.config.get('sunrise.pass_id'))
sv_identifier = ait.config.get('sunrise.sv_identifier')
utc_timestamp_now = (lambda: datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S"))
sv_name = ait.config.get('sunrise.sv_name')


@dataclass
class TaggedPacket:
    packet: bytearray
    packet_name: str
    packet_uid: int
    pass_number: int = pass_number
    vcid: int = -1
    processor_name: str = ""
    processor_counter: int = -1
    decoded_map: map = field(init=False)
    packet_time: astropy.time.core.Time = field(init=False) # Change varname to spacecraft_time_gps
    time_processed_utc: astropy.time.core.Time = field(init=False)
    field_alarms: dict = field(default_factory=dict)
    
    def subset_map(self):
        self.packet_time.format = 'iso'
        t_proc = str(self.time_processed_utc)
        t_event_time = str(self.packet_time)
        interests = {
            'sv_identifier': sv_identifier,
            'sv_name': sv_name,
            'packet_name': self.packet_name,
            'field_alarms': self.field_alarms,
            'decoded_packet': self.decoded_map,
            'time_processed_utc': t_proc,
            'packet_time': t_event_time,
            'vcid': self.vcid,
            'processor_name': self.processor_name,
            'processor_counter': self.processor_counter,
            'pass_number': self.pass_number
        }
        return interests

    def __post_init__(self):
        self.time_processed_utc = str(utc_timestamp_now())
