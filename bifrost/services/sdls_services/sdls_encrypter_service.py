from bifrost.common.service import Service
from ait.dsn.encrypt.encrypter import EncrypterFactory
import bifrost.services.uplink.tctf_service as tctf
from bifrost.services.sdls_services.sdls_utils import SDLS_Type, get_sdls_type
from ait.core import log
import asyncio
import traceback


class SDLS_Encrypter_Service(Service):
    """
    Add the following lines to config.yaml:

    - plugin:
      name: ait.dsn.plugins.Encrypter.Encrypter
      inputs:
        - TCTF_Manager

    Then configure the managed parameters in the config.yaml as
    required by the encryption service.
    """
    def __init__(self):
        super().__init__()
        self.security_risk = False
        self.report_time = 5
        self.loop.create_task(self.supervisor_tree())
        self.encrypter = EncrypterFactory().get()
        self.start()

    def __del__(self):
        self.encrypter.close()
        return

    def check_security_risk(self):
        # We never expected this plugin to be instantiated
        # if our intention was to run in SDLS_Type CLEAR mode.
        # We risk leaking keys and introduce unefined behavior.
        if any (t is (sdls_type := get_sdls_type()) for t in [SDLS_Type.CLEAR, SDLS_Type.FINAL]):
            print(f"CRITICAL CONFIGURATION ERROR: "
                  "found parameter expected_sdls_type: {sdls_type}. "
                  "This plugin expects <AUTH|ENC>. "
                  "If this is not an error, comment out "
                  "the encrypter plugin block. "
                  "We will refuse to process TCTFs.")
            self.security_risk = True
        self.security_risk = False
        return self.security_risk

    def connect(self):
        if self.check_security_risk():
            return
        self.encrypter.configure()
        self.encrypter.connect()
        log.info(f"Encryption services started.")

    async def reconfigure(self, topic, message, reply):
        await super().reconfigure(topic, message, reply)
        return

    async def process(self, topic, cmd_struct, reply):
        try:
            if self.security_risk or not topic == "Uplink.CmdMetaData.TCTF":
                # TCTF Manager should have never published to
                # TCTFs to us since we were expecting To oeprate in CLEAR mode.
                # If another plugin is attempting to encrypt something through us,
                # we will refuse.
                print(f""
                      "Dropping clear TCTF and halting further processing. "
                      "During startup we detected configuration parameter "
                      "dsn.sle.tctf.expected_sdls_type: CLEAR. "
                      "TCTF_Manager should not have been able to "
                      "publish to us in this state. "
                      "TCTFs should only be published by TCTF_Manager, "
                      f"but we received one from {topic}. "
                      "Check configuration parameter "
                      "`dsn.sle.tctf.expected_sdls_type`.")
                return

            
            # Pre-encryption size checks
            if not cmd_struct:
                log.error(f"received no data from {topic}")
                
            # Check for pre hand off to KMC size
            if tctf.check_tctf_size(cmd_struct.payload_bytes, get_sdls_type()):
                log.debug(f"TCTF size from {topic} is ok")
                
            else:
                log.error(f"Initial TCTF received from {topic}"
                          " is oversized! Undefined behavior will occur!")
                return

            # Encrypt and check
            data = bytearray(cmd_struct.payload_bytes)
            crypt_result = self.encrypter.encrypt(data)
            if crypt_result.errors:
                log.error(f"Got error during encryption:"
                          f"{crypt_result.errors}")
                return

            # Check KMC's addition of SDLS headers did not
            # violate the final desired TCTF size.
            if tctf.check_tctf_size(cmd_struct.payload_bytes, tctf.SDLS_Type.FINAL):
                log.debug(f"Encrypted TCTF is properly sized.")
                cmd_struct.frame_size_valid = True
            else:
                log.error(f"Encrypted TCTF is oversized! "
                          "Undefined behavior will occur! Dropping TCTF")
                return
            if cmd_struct.payload_bytes == crypt_result.result:
                log.error(f"Encryption result "
                          "was the same same as clear?")
                return
            else:
                # Looks good to publish
                cmd_struct.payload_bytes = crypt_result.result
                await self.publish("Uplink.CmdMetaData.SDLS", cmd_struct)
        except Exception as e:
            log.error(e)
            traceback.print_exc()
            

    async def supervisor_tree(self):
        async def monitor():
            while True:
                msg = {'state': self.encrypter.is_connected()}
                await self.publish('Bifrost.Monitors.KMC_Status', msg)
                await asyncio.sleep(self.report_time)

        async def auto_start():
            while True:
                if not self.encrypter.is_connected():
                    self.connect()
                await asyncio.sleep(self.report_time)

        self.loop.create_task(auto_start())
        self.loop.create_task(monitor())
            
        
