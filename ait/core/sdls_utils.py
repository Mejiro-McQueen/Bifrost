from enum import Enum, auto
import ait
import logging

log = logging.getLogger(__name__)

def get_sdls_type():
    config_prefix = 'dsn.sle.tctf.'
    """
    Return SDLS type from config.yaml
    """
    log_header = __name__ + "-> get_sdls_type=>"
    
    try:
        sdls_type_str = ait.config.get(config_prefix+'expected_sdls_type', None)
        sdls_type = SDLS_Type[sdls_type_str]
    except AttributeError:
        #  Config not ready
        return SDLS_Type.ENC
    except Exception as e:
        print(e)
        sdls_type = None
        log.debug(f"{log_header} Got None. {ait.config.get('dsn.sle.tctf.expected_sdls_type')}")
    if not sdls_type: 
        log.warn(f"{log_header} {config_prefix}expected_sdls_type parameter "
                 "was not found on config.yaml <CLEAR|AUTH|ENC>. "
                 "Assuming ENC.")
        sdls_type = SDLS_Type.ENC

    log.debug(f"found SDLS_Type: {sdls_type}")
    return sdls_type

class SDLS_Type(Enum):
    CLEAR = auto()
    ENC = auto()  # Authenticated Encryption (SDLS)
    AUTH = auto()  # Authentication Only (SDLS)
    # FINAL is for internal use.
    # It is treated the same as CLEAR
    # Used by Encrypter to signify that TCTF size check
    # should be done against final TCTF size instead of
    # the KMC hand off size that it must necessarily violate.
    FINAL = auto()
