import traceback
from bifrost.services.downlink.alarms import Alarm_Check

from bifrost.services.downlink.tagged_packet import TaggedPacket
from bifrost.services.downlink.frame_processors.utility import date_time_from_gps_s_ns
import struct
from ait.core import log
import sys
from ait.core import tlm

tlm_dict = tlm.getDefaultDict()


class CCSDS_Packet_Tagger:
    def __init__(self, vcid, processor_name):
        # This is junk
        self.counter = 0
        self.processor_name = processor_name
        self.vcid = vcid
        self.alarm_check = Alarm_Check()

    def __call__(self, packets):
        tagged_packets = []
        for packet in packets:
            try:
                self.counter += 1

                # Decoding
                uid = packet.primary_header['APPLICATION_PROCESS_IDENTIFIER']
                packet_def = tlm_dict.lookup_by_opcode(uid)  # Call to AIT
                if not packet_def:
                    log.error(f"Could not lookup {uid}: \n {self.processor_name} {self.vcid=} {packet=}")
                    continue
                    
                tagged_packet = TaggedPacket(packet, packet_def.name, uid)
                decoded_map = tlm.Packet(packet_def, packet.data)  # Call to AIT
                tagged_packet.decoded_map = dict(decoded_map.items())

                # Alarms Stamping
                tagged_packet.field_alarms = self.get_alarm_map(tagged_packet)

                # Time Stamping
                tagged_packet.packet_time = self.get_time_stamp(tagged_packet)
                
                # Metadata Stamping
                tagged_packet.packet_name = packet_def.name
                tagged_packet.processor_name = self.processor_name
                tagged_packet.processor_counter = self.counter
                tagged_packet.vcid = self.vcid
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

    def get_alarm_map(self, tagged_packet: TaggedPacket):
        field_alarms = {}
        for (packet_field, value) in tagged_packet.decoded_map.items():
            alarm_state, threshold = self.alarm_check(tagged_packet.packet_name,
                                                      packet_field, value)
            field_alarms[packet_field] = {'state': alarm_state.name,
                                          'threshold': threshold}
        return field_alarms

    def get_time_stamp(self, tagged_packet):
        # TODO, allow this function to be passed in when the depacketizer is initialized
        # Sometimes the secondary header is used instead of telemetry data
        gps_t_s = tagged_packet.decoded_map['seconds']
        gps_t_ns = tagged_packet.decoded_map['nanoseconds']
        return date_time_from_gps_s_ns(gps_t_s, gps_t_ns)
