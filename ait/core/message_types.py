from enum import Enum, auto
class MessageType(Enum):
    """
    Use these enums (pubsub topics) when the type of data published is more important than the module who published it. (e.g, OpenMCT doesn't care who vcid_router plugin is, but it certainly cares about the VCID_COUNT it periodically publishes.)

    Q: Why not just pass a string to publish?
    A: Type Safety. Another developer can search for data they're interested in.

    Use these types to annotate pub sub messages for modules that:
      1. Publishes multiple types of data.
      2. The published data is passed to an external application.
      3. A non plugin module is borrowing a plugin's publish function, making it not obvious that PUB/SUB messages are being emitted. (See RAF SLE interface for example).

    It's not necessary to use these types for inter plugin communication. Continue to use plugin names or strings to explicitly chain plugins together into a pipeline.

    USAGE:
        Send a message:
          msg_type = MessageType.VCID_COUNT
          self.publish((msg_type, packet_metadata_list), msg_type.name)
    """
    REAL_TIME_TELEMETRY = "realtime telemetry packets and metadata"
    STORED_TELEMETRY = "stored telemetry packets and metadata"
    VCID_COUNT = "vcid counts"
    LOG = "messages from log stream"
    CLTU_STATUS = "state of CLTU interface: <ACTIVE|READY|UNBOUND>, count of CLTU sent"
    RAF_DATA = "Raw frame from RAF Interface"
    RAF_STATUS = "state of RAF interface: <ACTIVE|READY|UNBOUND>, count of data received"
    TCP_STATUS = "Number of packets transferred/received"
    KMC_STATUS = "If message is received, KMC Plugin is active"
    SC_STATE_OF_HEALTH_REPORT = "Spacecraft state of health report"
    GRAFFITI_MAP = "DOT file containing AIT Pipeline" # TODO Do we want this, and does Joe want a DOT or PNG?
