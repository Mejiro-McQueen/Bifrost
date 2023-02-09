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
