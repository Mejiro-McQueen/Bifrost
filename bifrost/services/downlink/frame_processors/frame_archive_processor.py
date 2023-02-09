from bifrost.common.service import Service
from bifrost.common.disk_writer import Disk_Writer
from ait.core import log


class Frame_Archive_Processor(Service):
    """
    Calls stored file processor object and stores frames
    """
    def __init__(self):
        self.vcid_interests = {}
        super().__init__()
        self.start()
        return

    async def process(self, topic, tagged_frame, reply):
        if tagged_frame.vcid not in self.vcid_interests.keys():
            log.error(f"Unexpected VCID {tagged_frame.vcid},"
                      f"expected interest in one of {self.vcid_interests}.")
        else:
            frame_map = tagged_frame.subset_map()
            if tagged_frame.corrupt_frame:
                self.corrupt_writers[tagged_frame.vcid].write_to_disk(frame_map)
            else:
                if tagged_frame.vcid in self.writers:
                    self.writers[tagged_frame.vcid].write_to_disk(frame_map)
        return

    async def reconfigure(self, topic, data, reply):
        await super().reconfigure(topic, data, reply)
        path = "FrameArchive"
        self.frame_ext = '.AOS_TF'

        self.vcids = [vcid for (vcid, interested)
                      in self.vcid_interests.items() if interested]

        self.writers = {vcid: Disk_Writer(f"{path}", self.frame_ext, f"{vcid}")
                        for vcid in self.vcids}

        self.corrupt_writers = {vcid: Disk_Writer(f"{path}", self.frame_ext, f"{vcid}/corrupt")
                                for vcid in self.vcids}
