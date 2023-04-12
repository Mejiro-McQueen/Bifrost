from dataclasses import dataclass, field
import astropy.time


@dataclass
class TaggedPacket:
    packet: bytearray
    packet_name: str
    packet_uid: int
    pass_id: int = None
    sv_identifier: str = None
    sv_name: str = None
    time_processed_utc: str = None
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
            'sv_identifier': self.sv_identifier,
            'sv_name': self.sv_name,
            'packet_name': self.packet_name,
            'field_alarms': self.field_alarms,
            'decoded_packet': self.decoded_map,
            'time_processed_utc': t_proc,
            'packet_time': t_event_time,
            'vcid': self.vcid,
            'processor_name': self.processor_name,
            'processor_counter': self.processor_counter,
            'pass_id': self.pass_id
        }
        return interests
