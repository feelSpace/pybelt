#! /usr/bin/env python
# encoding: utf-8
import logging
import sys

import serial
import pybelt
from serial.tools import list_ports


def main():

    # Config logger to output pybelt debug messages on console
    logger = pybelt.logger
    logger.setLevel(logging.DEBUG)
    sh = logging.StreamHandler(sys.stdout)
    sh_format = logging.Formatter('\033[92m %(levelname)s: %(message)s \033[0m')
    sh.setFormatter(sh_format)
    sh.setLevel(logging.DEBUG)
    logger.addHandler(sh)

    # Retrieve the list of serial COM ports
    ports = serial.tools.list_ports.comports()

    # Output
    if ports is None or len(ports) == 0:
        print("No serial port found.")
    else:
        if len(ports) == 1:
            print("One serial port found.")
        else:
            print("{} serial ports found.".format(len(ports)))
        for comm_port in ports:
            print("Port: {}".format(comm_port[0]))


if __name__ == "__main__":
    main()
