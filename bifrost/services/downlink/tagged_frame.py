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

    def subset_map(self):
        res = {'channel_counter': self.channel_counter,
               'absolute_counter': self.absolute_counter,
               'vcid': self.vcid,
               'corrupt_frame': self.corrupt_frame,
               'out_of_sequence': self.out_of_sequence,
               'is_idle': self.idle,
               'frame': self.frame.hex()}
        return res

    def __repr__(self):
        s = f'frame={self.frame.hex()}, '
        s += f'vcid={self.vcid}, '
        s += f'channel_counter={self.channel_counter}, '
        s += f'absolute_counter={self.absolute_counter}, '
        s += f'corrupt_frame={self.corrupt_frame}, '
        s += f'out_of_sequence={self.out_of_sequence}, '
        s += f'idle={self.idle}'
        return s
