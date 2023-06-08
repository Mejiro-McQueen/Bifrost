from dataclasses import dataclass, field
import astropy.time


@dataclass
class TaggedPacket:
    """
    Represents a packet and associated metadata.
    This data contains additional components necessary for Influx and OpenMCT.

    :param packet: Raw packet in hex.
    :param packet_name: Packet's name
    :param uid: AIT dictionary index (kind of useless)
    :param pass_id: The pass id for this Bifrost instance.
    :param sv_identifier: The pass id associated with this Bifrost instance.
    :param sv_name: The space vehicle name associated with this Bifrost instance.
    :param vcid: The virtual channel id that originated this packet.
    :param processor_name: The common name of the processor for vcid
    :param processor_counter: The number of times the vcid processor has executed.
    :param decoded_map: The dictionary containing the decoded packet.
    :param packet_time: The timetstamp derived from the packet.
    :param time_processed_utc: The UTC timestamp of when this packet was decoded.
    :param field_alarms: A map with type {fieldname: (Alarm Color, Threshold)}
    :returns: A tagged packet. Marshall as soon as possible.

    """
    packet: bytearray
    packet_name: str
    packet_uid: int
    pass_id: int = None
    sv_identifier: str = None
    sv_name: str = None
    vcid: int = -1
    processor_name: str = ""
    processor_counter: int = -1
    decoded_packet: map = field(init=False)
    packet_time: astropy.time.core.Time = field(init=False) # Change varname to spacecraft_time_gps
    time_processed_utc: astropy.time.core.Time = field(init=False)
    field_alarms: dict = field(default_factory=dict)

    def __post_init__(self):
        self.packet_time = None
        self.time_processed_utc = None
    
    def marshall(self):
        self.packet_time.format = 'iso'
        interests = {'data_type': type(self).__name__ , **self.__dict__.copy()}
        interests['ccsds_packet'] = interests.pop('packet')
        interests['time_processed_utc'] = str(self.time_processed_utc)
        interests['packet_time'] = str(self.packet_time)
        return interests
