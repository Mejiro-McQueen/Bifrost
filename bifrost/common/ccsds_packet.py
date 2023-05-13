from enum import Enum, auto
from bitstring import BitArray
from colorama import Fore
from bifrost.common.loud_exception import with_loud_exception


class Packet_State(Enum):
    COMPLETE = auto()
    UNDERFLOW = auto()
    SPILLOVER = auto()
    IDLE = auto()


class HeaderKeys(Enum):
    PACKET_VERSION_NUMBER = slice(0, 3)
    PACKET_TYPE = slice(3, 4)
    SEC_HDR_FLAG = slice(4, 5)
    APPLICATION_PROCESS_IDENTIFIER = slice(5, 16)
    SEQUENCE_FLAGS = slice(16, 18)
    PACKET_SEQUENCE_OR_NAME = slice(18, 32)
    PACKET_DATA_LENGTH = slice(32, 48)


class CCSDS_Packet():

    @with_loud_exception
    def __init__(self, PACKET_VERSION_NUMBER=0, PACKET_TYPE=0,
                 SEC_HDR_FLAG=0, APPLICATION_PROCESS_IDENTIFIER=0,
                 SEQUENCE_FLAGS=0, PACKET_SEQUENCE_OR_NAME=0,
                 PACKET_DATA_LENGTH=0, data=b''):
        """Don't call this directly, use decode"""
        self.data = data
        self.primary_header = {}
        self.primary_header[HeaderKeys.PACKET_VERSION_NUMBER.name] = PACKET_VERSION_NUMBER
        self.primary_header[HeaderKeys.PACKET_TYPE.name] = PACKET_TYPE
        self.primary_header[HeaderKeys.SEC_HDR_FLAG.name] = SEC_HDR_FLAG
        self.primary_header[HeaderKeys.APPLICATION_PROCESS_IDENTIFIER.name] = APPLICATION_PROCESS_IDENTIFIER
        self.primary_header[HeaderKeys.SEQUENCE_FLAGS.name] = SEQUENCE_FLAGS
        self.primary_header[HeaderKeys.PACKET_SEQUENCE_OR_NAME.name] = PACKET_SEQUENCE_OR_NAME
        if not PACKET_DATA_LENGTH:
            self.primary_header[HeaderKeys.PACKET_DATA_LENGTH.name] = len(data) - 1
        else:
            self.primary_header[HeaderKeys.PACKET_DATA_LENGTH.name] = PACKET_DATA_LENGTH
        self.secondary_header = {}  # TODO Handle secondary header

        self.encoded_packet = bytes().hex()
        self.secondary_header_encoded = bytes()
        self.error = None

    @with_loud_exception
    def marshall(self):
        s = {
            'data_type': type(self).__name__,
            'primary_header': self.primary_header,
            'secondary_header_encoded': self.secondary_header_encoded.hex(),
            'data': self.data.hex(),
            'error': self.error,
            'is_idle': self.is_idle(),
            'is_complete': self.is_complete(),
            'encoded_packet': self.encoded_packet.hex(),
            'missing': self.get_missing(),
            'next_index': self.get_next_index(),
        }
        return s


    @with_loud_exception
    def __repr__(self):
        return str(self.marshall())

    @staticmethod
    @with_loud_exception
    def decode(packet_bytes, secondary_header_length=0):
        """Generate a packet"""
        data_length = int.from_bytes(packet_bytes[4:6], 'big')
        if not data_length: # regular check is apid 111111....
            #log.debug("Underflow: Insufficient Data")
            return (Packet_State.UNDERFLOW, None)

        if set(packet_bytes) == {224}:
            #log.debug(f"Idle Packet")
            return (Packet_State.IDLE, None)

        actual_packet = packet_bytes[:6 + data_length + 1]
        header_bits = BitArray(actual_packet[0:6]).bin
        data = actual_packet[6:]
        decoded_header = {}
        for key in HeaderKeys:
            decoded_header[key.name] = int(header_bits[key.value], 2)

        decoded_header['data'] = data
        p = CCSDS_Packet(**decoded_header)
        p.encoded_packet = actual_packet
        #rest = packet_bytes[6+data_length+1:]

        if decoded_header[HeaderKeys.SEC_HDR_FLAG.name] and secondary_header_length:
            p.secondary_header = data[:secondary_header_length]
            p.secondary_header_encoded = data[:secondary_header_length]
            p.data = data[secondary_header_length:]

        p = p.marshall()
        if p['is_complete']:
            #log.debug(f"OK, Packet Complete: {p}")
            return (Packet_State.COMPLETE, p)
        else:
            #log.debug(f"Not Ok, Packet spilled over: {p}")
            return (Packet_State.SPILLOVER, p)

    @with_loud_exception
    def is_complete(self):
        return not bool(self.get_missing())

    @with_loud_exception
    def is_idle(self):
        return self.primary_header[HeaderKeys.APPLICATION_PROCESS_IDENTIFIER.name] == 0b11111111111

    @with_loud_exception
    def get_missing(self):
        m = (g := self.primary_header[HeaderKeys.PACKET_DATA_LENGTH.name]+1) - (q := len(self.data))
        m -= (k := len(self.secondary_header_encoded))
        #print(f"{m=} {g=} {q=} {k=}")
        return m

    @with_loud_exception
    def get_next_index(self):
        return 6 + self.primary_header[HeaderKeys.PACKET_DATA_LENGTH.name] + 1

    @with_loud_exception
    def __str__(self):
        return str(self.__class__) + ": " + str(self.__dict__)

    @staticmethod
    @with_loud_exception
    def encode(data, application_process_identifier,
               packet_version_number=0,
               packet_type=1, sec_hdr_flag=0,
               sequence_flags=0, packet_sequence_or_name=0):
        
        packet_version_number = BitArray(bin=format(0, '03b')) #  Version 1 CCSDS Packet
        packet_type = BitArray(bin=format(packet_type, '01b'))  # Telecommand; We don't generate telemetry or reports.
        secondary_header_flag = BitArray(bin=format(0, '01b')) # No Secondary header for now
        apid = BitArray(bin=format(int(application_process_identifier[2:]), '011b'))
        sequence_flags = BitArray(bin='11')
        if isinstance(packet_sequence_or_name, str):
            # TODO: Truncate to 14b
            packet_sequence_count = BitArray(bytes=packet_sequence_or_name.encode('ASCII'))
        else:
            packet_sequence_count = BitArray(bin=format(packet_sequence_or_name, '014b'))

        packet_length = BitArray(bin=format(len(data)-1, '016b'))
        data = BitArray(bytes=data)

        packet = sum([packet_version_number, packet_type, secondary_header_flag,
                     apid, sequence_flags, packet_sequence_count, packet_length, data])
        print(len(packet))
        return packet.bytes

        # TODO Handle packet segmentation
