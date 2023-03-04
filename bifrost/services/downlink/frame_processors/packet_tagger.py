from ait.core import log
from ait.core import tlm
from bifrost.services.downlink.alarms import Alarm_Check
from bifrost.services.downlink.tagged_packet import TaggedPacket
import struct
import sys

tlm_dict = tlm.getDefaultDict()  # Call to AIT


class CCSDS_Packet_Tagger:
    """Timestamp is a function that provides a datetime like object whenever a packet is passed into it"""
    def __init__(self, vcid, processor_name, timestamp_from_packet):
        # This is junk
        self.counter = 0
        self.processor_name = processor_name
        self.vcid = vcid
        self.alarm_check = Alarm_Check()
        self.timestamp_from_packet = timestamp_from_packet
        
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
                tagged_packet.packet_time = self.timestamp_from_packet(tagged_packet)
                
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
