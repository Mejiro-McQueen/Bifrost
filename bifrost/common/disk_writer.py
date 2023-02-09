import errno
import json as json
import ait
from ait.core import log
from pathlib import Path
from datetime import datetime

pass_number = str(ait.config.get('sunrise.pass_id'))
sv_name = ait.config.get('sunrise.sv_name')
downlink_path = Path(ait.config.get('sunrise.data_path')) / str(pass_number) / sv_name / 'downlink' 
utc_timestamp_now = (lambda: datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S"))


class Disk_Writer():
    """
    Allows processors to write a dictionary to disk.
    """
    # This is weird
    def __init__(self, path, extension, fname, subpath=""):
        self.path = (downlink_path / path / subpath
                     / (f"{fname}_{sv_name}_{pass_number}{extension}.ndjson"))

        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.f = open(self.path, "a")
        except Exception as e:
            if e.errno == errno.ENOSPC:
                log.error("Out of disk space!")
            self.loop.create_task(self.publish('Bifrost.Messages.Error.Panic.WriteableToDisk', e))
            raise e

        self.first_entry = True
        self.end_pos = self.f.tell()

    def write_to_disk(self, data: map, event_time_gps=None):
        r = {}
        if event_time_gps:
            r['event_time_gps'] = str(event_time_gps)

        r['time_processed'] = str(utc_timestamp_now())
        r['data'] = data

        r = json.dumps(r, indent=4)
        try:
            self.f.write(r)
            self.f.write("\n\n")
            self.f.flush()

        except Exception as e:
            log.error(f"Encountered error while"
                      f" writing {self.path}: {e}")

        return (self.path, self.end_pos)

    def __del__(self):
        self.close()
