from astropy.time import Time
from datetime import datetime

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


def packet_time_stamp_from_gps_s_ns(tagged_packet):
    gps_t_s = tagged_packet.decoded_map['seconds']
    gps_t_ns = tagged_packet.decoded_map['nanoseconds']
    return date_time_from_gps_s_ns(gps_t_s, gps_t_ns)


def time_processed(tagged_packet):
    return gps_timestamp_now()


utc_timestamp_now = (lambda: datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S"))

gps_timestamp_now = (lambda: Time(Time.now(), format='gps', scale='tai', precision=9))
