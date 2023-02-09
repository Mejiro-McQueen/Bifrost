import traceback
from bifrost.services.downlink.alarms import Alarm_Check

from bifrost.services.downlink.tagged_packet import TaggedPacket
from bifrost.services.downlink.tagged_frame import TaggedFrame
from bifrost.services.downlink.frame_processors.utility import date_time_from_gps_s_ns
import struct
from ait.core import log
import sys
from sunrise.frame_processors.packet_utils import SunRISEPacketUtils
from ait.core import tlm


class Depacketizer():
    # Allows objects to depacketize TaggedFrames
    """
    Return and track a list of CCSDS packets from a TaggedFrame.
    Option to drop corrupt frames
    """
    def __init__(self, depacketizer):
        self.deframer_type = depacketizer
        self.deframer = self.deframer_type()
        self.counter = 0
        self.alarm_check = Alarm_Check()

    async def depacketize(self, tagged_frame: TaggedFrame):
        if tagged_frame.corrupt_frame:
            log.warn(f"{self.processor_name} Dropping corrupt frame.")
            self.deframer = self.deframer_type()
            return []
        if tagged_frame.out_of_sequence:
            log.warn(f"{self.processor_name} Dropping out of sequence frame on VCID {tagged_frame.vcid}")
            self.deframer = self.deframer_type()
            return []

        try:
            raw_packets = self.deframer.depacketize(tagged_frame.frame)
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
            await self.publish('Bifrost.Messages.Error.Panic.Depacketizer', e)
            raise e

        # This is junk
        tagged_packets = []
        for i in raw_packets:
            try:
                tagged_packet = SunRISEPacketUtils.tag_packet(i, self.pass_id, self.vcid)
                if not tagged_packet:
                    continue

                if tagged_packet:
                    self.counter += 1
                    self.decode_tagged_packet(tagged_packet)
                    tagged_packet.processor_name = self.processor_name
                    tagged_packet.processor_counter = self.counter
                    tagged_packet.vcid = tagged_frame.vcid
                    tagged_packets.append(tagged_packet)
            except struct.error as e:
                log.error(f"Could not decode tagged_packet: {e}")
                continue
            except IndexError as e:
                log.error(f"Could not decode tagged_packet: {e}")
                continue
            except Exception as e:
                log.error(f"Got error finalizing tagging: {e}")
                excp = sys.exc_info()
                log.error(excp)
                raise e
        return tagged_packets

    def decode_tagged_packet(self, tagged_packet: TaggedPacket):
        # Decodes a packet via side effects
        try:
            decoded_map = tlm.Packet(tagged_packet.packet_definition,
                                     tagged_packet.user_data_field)

            tagged_packet.decoded_map = dict(decoded_map.items())

            tagged_packet.field_alarms = self.get_alarm_map(tagged_packet)

            gps_t_s = decoded_map['seconds']
            gps_t_ns = decoded_map['nanoseconds']
            tagged_packet.event_time_gps = date_time_from_gps_s_ns(gps_t_s,
                                                                   gps_t_ns)
            return
        except struct.error as e:
            raise e
        except IndexError as e:
            raise e
        except Exception as e:
            log.error(f"Got an error while constructing tagged packet {e}")
            excp = sys.exc_info()
            log.error(excp)
            raise e

    def get_alarm_map(self, tagged_packet: TaggedPacket):
        field_alarms = {}
        for (packet_field, value) in tagged_packet.decoded_map.items():
            alarm_state, threshold = self.alarm_check(tagged_packet.packet_name,
                                                      packet_field, value)
            field_alarms[packet_field] = {'state': alarm_state.name,
                                          'threshold': threshold}
        return field_alarms
