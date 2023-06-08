from dataclasses import dataclass

@dataclass
class TaggedFrame:
    frame: bytearray
    vcid: int
    channel_counter: int = 0
    absolute_counter: int = 0
    corrupt_frame: bool = False
    out_of_sequence: bool = False
    idle: bool = False

    def marshall(self):
        res = {
            'data_type': type(self).__name__,
            'frame': self.frame,
            'channel_counter': self.channel_counter,
            'absolute_counter': self.absolute_counter,
            'vcid': self.vcid,
            'corrupt_frame': self.corrupt_frame,
            'out_of_sequence': self.out_of_sequence,
            'is_idle': self.idle,
        }
        return res

    def __repr__(self):
        return str(self.marshall())
