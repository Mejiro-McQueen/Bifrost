from bifrost.common.service import Service
from pathlib import Path
from bifrost.services.extra.synchronization_service import SyncByte
from bifrost.common.loud_exception import with_loud_exception, with_loud_coroutine_exception


class Raw_Frame_Archive_Service(Service):
    """
    This service is intended to archive frames.
    Creates a directory with incrementing file names.

    This archive can be reinjected into AIT as part of automated testing.

    Customize the template within the services.yaml block:

    - service:

        archive_dir: /data/archive
        file_extension: AOS_TF


    - plugin:
        name: bifrost.services.testing.archive_services.Raw_Frame_Archive_Service
        disabled: False
        frame_ext: '.AOS_TF'
        vcid_interests:
          1: True
          2: True
          4: True
          63: False
        streams:
          archive:
            - 'Telemetry.AOS.Raw'
    """

    @with_loud_exception
    def __init__(self):
        super().__init__()
        self.start()

    @with_loud_coroutine_exception
    async def reconfigure(self, topic, message, reply):
        if hasattr(self, 'f'):
            self.f.close()
        data_path = await self.config_request('global.paths.data_path')
        assert data_path
        pass_id = await self.config_request('global.mission.pass_id')
        assert pass_id is not None
        sv_name = await self.config_request('instance.space_vehicle.sv_name')
        assert sv_name

        await super().reconfigure(topic, message, reply)

        self.archive_dir = Path(f"{data_path}/{pass_id}/{sv_name}/downlink/frames/frames{self.frame_extension}")
        Path(self.archive_dir.parent).mkdir(parents=True, exist_ok=True)

        self.f = self.archive_dir.open('ab')
        self.syncbyte = SyncByte(b'\xbe\xef', 4)
        self.vcids = [vcid for (vcid, interested)
                      in self.vcid_interests.items() if interested]
        return

    @with_loud_coroutine_exception
    async def archive(self, topic, data, reply):
        vcid = data[1] & 0x3F  # TODO: We'll fix this later
        if vcid in self.vcids and self.f:
            self.f.write(self.syncbyte(data))
