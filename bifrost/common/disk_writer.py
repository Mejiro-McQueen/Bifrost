from bifrost.common.loud_exception import with_loud_exception
import errno
import json as json
from ait.core import log
from pathlib import Path

class Disk_Writer():
    """
    Allows processors to write a dictionary to disk.
    TODO: Everyone should be requesting that monitor write to disk
    """
    
    @with_loud_exception
    def __init__(self, path, extension, fname, pass_id, downlink_path, sv_name,subpath="",):
        self.path = Path(f"{downlink_path} / {path} / {subpath} / {fname}_{sv_name}_{pass_id}{extension}.ndjson")

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

    @with_loud_exception
    def write_to_disk(self, data: map, timestamp, event_time_gps=None):
        r = {}
        if event_time_gps:
            r['event_time_gps'] = str(event_time_gps)

        r['time_processed'] = str(timestamp)
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

    @with_loud_exception
    def __del__(self):
        self.close()
