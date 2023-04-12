from bifrost.common.service import Service
from bifrost.common.loud_exception import with_loud_coroutine_exception, with_loud_exception
from bifrost.common.disk_writer import Disk_Writer
from bifrost.common.time_utility import utc_timestamp_now
from ait.core import log


class Frame_Archive_Processor(Service):
    """
    Calls stored file processor object and stores frames
    """
    @with_loud_exception
    def __init__(self):
        self.vcid_interests = {}
        super().__init__()
        self.start()
        return

    @with_loud_coroutine_exception
    async def process(self, topic, tagged_frame, reply):
        if tagged_frame.vcid not in self.vcid_interests.keys():
            log.error(f"Unexpected VCID {tagged_frame.vcid},"
                      f"expected interest in one of {self.vcid_interests}.")
        else:
            frame_map = tagged_frame.subset_map()
            if tagged_frame.corrupt_frame:
                self.corrupt_writers[tagged_frame.vcid].write_to_disk(frame_map, utc_timestamp_now())
            else:
                if tagged_frame.vcid in self.writers:
                    self.writers[tagged_frame.vcid].write_to_disk(frame_map, utc_timestamp_now())
        return

    @with_loud_coroutine_exception
    async def reconfigure(self, topic, data, reply):
        self.downlink_path = await self.config_request_downlink_path()
        self.pass_id = await self.config_request_pass_id()
        self.sv_name = await self.config_request_sv_name()
        await super().reconfigure(topic, data, reply)
        path = "FrameArchive"
        self.frame_ext = '.AOS_TF'

        self.vcids = [vcid for (vcid, interested)
                      in self.vcid_interests.items() if interested]

        self.writers = {vcid: Disk_Writer(f"{path}", self.frame_ext, f"{vcid}",
                                          self.pass_id, self.downlink_path,
                                          self.sv_name)
                        for vcid in self.vcids}

        self.corrupt_writers = {vcid: Disk_Writer(f"{path}", self.frame_ext,
                                                  f"{vcid}/corrupt", self.sv_name,
                                                  self.downlink_path, self.sv_name)
                                for vcid in self.vcids}
