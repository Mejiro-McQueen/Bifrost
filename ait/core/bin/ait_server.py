#!/usr/bin/env python

import fcntl
import os
import sys

"""
Usage: ait-server

Start the AIT telemetry server for managing telemety streams,
command outputs, processing handlers, and plugins.
"""

import argparse

from ait.core.server import Server


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    args = ap.parse_args()  # noqa

    if running():
        print("An instance of AIT is already running or could not obtain /tmp/ait_server.lock flock.")
        sys.exit(-1)
    
    tlm_cmd_serv = Server()
    tlm_cmd_serv.wait()

if __name__ == "__main__":
    main()

def running():
    lock_file = os.open(f"/tmp/ait_server.lock", os.O_WRONLY | os.O_CREAT)
    try:
        fcntl.lockf(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        already_running = False
    except IOError:
        already_running = True
    return already_running
