#! /usr/bin/env python
# encoding: utf-8
import logging
import sys

import serial
import pybelt
from serial.tools import list_ports

from pybelt.belt_controller import BeltController, BeltConnectionState
from pybelt.belt_scanner import BeltScanner


def main():

    belt_controller = BeltController()

    # Config logger to output pybelt debug messages on console
    logger = pybelt.logger
    logger.setLevel(logging.DEBUG)
    sh = logging.StreamHandler(sys.stdout)
    sh_format = logging.Formatter('\033[92m %(levelname)s: %(message)s \033[0m')
    sh.setFormatter(sh_format)
    sh.setLevel(logging.DEBUG)
    logger.addHandler(sh)

    # Ask for the interface
    interface = input("Connect via Bluetooth or USB? [b,u]")

    if interface.lower() == "b":
        # Scan for advertising belt
        with pybelt.belt_scanner.create() as scanner:
            print("Start BLE scan.")
            belts = scanner.scan()
            print("BLE scan completed.")
        if len(belts) == 0:
            print("No belt found.")
            return 0
        if len(belts) > 1:
            print("Select the belt to connect.")
            for i, belt in enumerate(belts):
                print("{}. {} - {}".format((i+1), belt.name, belt.address))
            belt_selection = input("[1-{}]".format(len(belts)))
            try:
                belt_selection_int = int(belt_selection)
            except:
                print("Unrecognized input.")
                return 0
            print("Connect the belt.")
            belt_controller.connect(belts[belt_selection_int-1])
        else:
            print("Connect the belt.")
            belt_controller.connect(belts[0])

    elif interface.lower() == "u":
        # List serial COM ports
        ports = serial.tools.list_ports.comports()
        if ports is None or len(ports) == 0:
            print("No serial port found.")
            return 0
        if len(ports) == 1:
            connect_ack = input("Connect using {}? [y,n]".format(ports[0][0]))
            if connect_ack.lower() == "y" or connect_ack.lower() == "yes":
                print("Connect the belt.")
                belt_controller.connect(ports[0][0])
            else:
                print("Unrecognized input.")
                return 0
        else:
            print("Select the serial COM port to use.")
            for i, port in enumerate(ports):
                print("{}. {}".format((i + 1), port[0]))
            belt_selection = input("[1-{}]".format(len(ports)))
            try:
                belt_selection_int = int(belt_selection)
            except:
                print("Unrecognized input.")
                return 0
            print("Connect the belt.")
            belt_controller.connect(ports[belt_selection_int - 1][0])

    else:
        print("Unrecognized input.")
        return 0

    # Connection result
    if belt_controller.get_connection_state() == BeltConnectionState.CONNECTED:
        print("Connection successful.")
        print("Belt firmware version: {}".format(belt_controller.get_firmware_version()))
        print("Belt mode: {}".format(belt_controller.get_belt_mode()))
        print("Belt default vibration intensity: {}".format(belt_controller.get_default_intensity()))
        print("Disconnect belt.")
    else:
        print("Connection failed.")
    belt_controller.disconnect_belt()
    return 0


if __name__ == "__main__":
    main()
