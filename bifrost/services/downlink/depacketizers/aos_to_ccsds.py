from ait.core import log
from ait.dsn.sle.frames import AOSTransFrame
from colorama import Fore, Back, Style
from bifrost.common.ccsds_packet import Packet_State, CCSDS_Packet


class AOS_to_CCSDS_Depacketization():
    def __init__(self):
        self.bytes_from_previous_frames = bytes()
        self.happy_customers = 0

    def depacketize(self, data):
        log.debug("NEW")

        def attempt_packet(data):
            stat, p = CCSDS_Packet.decode(data)
            if stat == Packet_State.COMPLETE:
                log.debug(f"{Fore.GREEN} Got a packet! {Fore.RESET}")
                accumulated_packets.append(p.encoded_packet)
                self.bytes_from_previous_frames = bytes()
                return p.get_next_index()

            elif stat == Packet_State.SPILLOVER:
                log.debug(f"{Fore.MAGENTA} SPILLOVER missing {p.get_missing()} bytes {Fore.RESET}")
                self.bytes_from_previous_frames = data
                return None

            elif stat == Packet_State.UNDERFLOW:
                log.debug(f"{Fore.RED} UNDERFLOW {data=} {Fore.RESET}")
                self.bytes_from_previous_frames = data
                return None

            elif stat == Packet_State.IDLE:
                log.debug(f"{Fore.YELLOW} IDLE {Fore.RESET}")
                return None

        def handle_spillover_packet(data):
            p = attempt_packet(self.bytes_from_previous_frames + data)
            if p:
                log.debug(f"{Fore.CYAN} Picked up a packet! {Fore.RESET}")

        accumulated_packets = []
        AOS_frame_object = AOSTransFrame(data)

        if AOS_frame_object.is_idle_frame:
            log.debug("Dropping idle frame!")
            return accumulated_packets

        if AOS_frame_object.get('mpdu_is_idle_data'):
            print("Idle! Packet!")
            return accumulated_packets

        first_header_pointer = AOS_frame_object.get('mpdu_first_hdr_ptr')
        mpdu_packet_zone = AOS_frame_object.get('mpdu_packet_zone')

        log.debug(f"{first_header_pointer=} ")
        if first_header_pointer != 0 and self.bytes_from_previous_frames:
            log.debug(f"Handling spare packet: {first_header_pointer=}")
            handle_spillover_packet(mpdu_packet_zone[:first_header_pointer])

        pointer = first_header_pointer
        j = 1
        while (maybe_next_packet := mpdu_packet_zone[pointer:]):
            #print(maybe_next_packet.hex())
            #print(f"{j=}")
            j += 1
            next_index = attempt_packet(maybe_next_packet)
            if not next_index:
                break
            pointer += next_index

        return accumulated_packets
