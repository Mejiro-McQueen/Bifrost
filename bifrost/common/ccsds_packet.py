from enum import Enum, auto
from bitstring import BitArray
from colorama import Fore


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
            self.primary_header[HeaderKeys.PACKET_DATA_LENGTH.name] = len(data)-1
        else:
            self.primary_header[HeaderKeys.PACKET_DATA_LENGTH.name] = PACKET_DATA_LENGTH
        self.secondary_header = {}  # TODO Handle secondary header

        self.encoded_packet = bytes()
        self.error = None

    def __repr__(self):
        s = str({'primary_header': self.primary_header,
                 'secondary_header': self.secondary_header,
                 'encoded_packet': self.encoded_packet.hex()})
        return s

    @staticmethod
    def decode(packet_bytes, secondary_header_length=6):
        """Generate a packet"""
        data_length = int.from_bytes(packet_bytes[4:6], 'big')
        if not data_length: # regular check is apid 111111....
            #log.warn("Underflow: Insufficient Data")
            return (Packet_State.UNDERFLOW, None)

        if set(packet_bytes) == {224}:
            #log.info(f"Idle Packet")
            return (Packet_State.IDLE, None)
            return

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
            
        if p.is_complete():
            # This looks good, let's move it out, add the new map fields, and rewrite get_missing 
            if decoded_header[HeaderKeys.SEC_HDR_FLAG.name] and secondary_header_length:
                p.secondary_header = data[:secondary_header_length]
                p.data = data[secondary_header_length:]
            return (Packet_State.COMPLETE, p)
        else:
            return (Packet_State.SPILLOVER, p)

    def is_complete(self):
        return not bool(self.get_missing())

    def is_idle(self):
        return self.primary_header[HeaderKeys.APPLICATION_PROCESS_IDENTIFIER.name] == 0b11111111111

    def get_missing(self):
        m = (g := self.primary_header[HeaderKeys.PACKET_DATA_LENGTH.name]+1) - (q := len(self.data))
        #print(f"{m=} {g=} {q=}")
        return m

    def get_next_index(self):
        return 6 + self.primary_header[HeaderKeys.PACKET_DATA_LENGTH.name] + 1

    def __str__(self):
        return str(self.__class__) + ": " + str(self.__dict__)

    def encode(self):
        if self.encoded_packet:
            return self.encoded_packet

        new = BitArray()
        for (k, v) in self.primary_header.items():
            size = k.value.start - (k.value.stop - 1)
            padded_segment = format(v, f'0{size}b')
            segment = BitArray(bin=padded_segment)
            new.append(segment)
        new.append(self.data)
        self.encoded_packet = new.bytes
        return self.encoded_packet
