#! /usr/bin/env python
# encoding: utf-8

import serial
import pybelt
from serial.tools import list_ports

from examples.connect import setup_logger


def main():
    setup_logger()

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
