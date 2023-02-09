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
    packet_definition: str
    user_data_field: bytearray
    pass_number: int
    vcid: int = -1
    processor_name: str = ""
    processor_counter: int = -1
    decoded_map: map = field(init=False)
    event_time_gps: astropy.time.core.Time = field(init=False) # Change varname to spacecraft_time_gps
    time_processed_utc: astropy.time.core.Time = field(init=False)
    field_alarms: dict = field(default_factory=dict)
    packet_uid: int = field(init=False)
    packet_name: str = field(init=False)
    
    def subset_map(self):
        self.event_time_gps.format = 'iso'
        t_proc = str(self.time_processed_utc)
        t_event_time = str(self.event_time_gps)
        interests = {
            'sv_identifier': sv_identifier,
            'sv_name': sv_name,
            'packet_name': self.packet_name,
            'field_alarms': self.field_alarms,
            'decoded_packet': self.decoded_map,
            'time_processed_utc': t_proc,
            'event_time_gps': t_event_time,
            'vcid': self.vcid,
            'processor_name': self.processor_name,
            'processor_counter': self.processor_counter,
            #'packet_uid': self.packet_uid,
            #'user_data_field': self.user_data_field,
            'pass_number': self.pass_number
        }
        return interests

    def __post_init__(self):
        self.packet_uid = self.packet_definition.uid
        self.packet_name = self.packet_definition.name
        self.time_processed_utc = str(utc_timestamp_now())
