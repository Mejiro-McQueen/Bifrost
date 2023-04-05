from bifrost.common.loud_exception import with_loud_exception
import traceback
from bifrost.services.downlink.tagged_frame import TaggedFrame
import struct
from ait.core import log


class Frame_Depacketizer():
    # Add option to no drop out of sequence
    def __init__(self, depacketization_type, processor_name,
                 enforce_sequence=False,
                 secondary_header_length=0):
        self.deframer_type = depacketization_type  # Use to reinit depacketizer
        self.processor_name = processor_name
        self.enforce_sequence = enforce_sequence
        self.secondary_header_length = secondary_header_length
        self.deframer = self.deframer_type(secondary_header_length)

    @with_loud_exception
    def __call__(self, tagged_frame: TaggedFrame):
        if tagged_frame.corrupt_frame:
            log.warn(f"{self.processor_name} Dropping corrupt frame.")
            self.deframer = self.deframer_type(self.secondary_header_length)
            return []
        
        if self.enforce_sequence and tagged_frame.out_of_sequence:
            log.warn(f"{self.processor_name} Dropping out of sequence frame on VCID {tagged_frame.vcid}")
            log.warn(f"{tagged_frame}")
            self.deframer = self.deframer_type(self.secondary_header_length)
            return []

        try:
            packets = self.deframer.depacketize(tagged_frame.frame)
            return packets
        except struct.error as e:
            log.error(f"Could not process frames: {e}")
            return []
        except UnicodeEncodeError as e:
            log.error(f"Could not process frames: {e}")
            return []
        except Exception as e:
            log.error(f"Got an error during depacketization: {e}")
            traceback.print_exc()
            log.error(e)
            raise e

        
