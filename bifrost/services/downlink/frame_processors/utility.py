from datetime import datetime
from astropy.time import Time
import ait
from ait.core import tlm
from pathlib import Path

# Customization
STRICT = False

pass_number = str(ait.config.get('sunrise.pass_id'))

sv_name = ait.config.get('sunrise.sv_name')
downlink_path = Path(ait.config.get('sunrise.data_path')) / str(pass_number) / sv_name / 'downlink' 
sv_identifier = ait.config.get('sunrise.sv_identifier')
utc_timestamp_now = (lambda: datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S"))
gps_timestamp_now = (lambda: Time(Time.now(), format='gps', scale='tai', precision=9))
startup_time = utc_timestamp_now()

file_downlink_packet_dir = (downlink_path / "file_downlink")

file_downlink_packet_dir.mkdir(parents=True, exist_ok=True)

tlm_dict = tlm.getDefaultDict()
canonical_astropy_time_from_gps = (lambda gps_time:
                                   Time(gps_time,
                                        format='gps',
                                        scale='tai',
                                        precision=9))


def date_time_from_gps_s_ns(gps_seconds, gps_nano_seconds):
    gps_float = float(".".join([str(gps_seconds),
                                str(gps_nano_seconds)]))
    t_gps = canonical_astropy_time_from_gps(gps_float)
    return t_gps
