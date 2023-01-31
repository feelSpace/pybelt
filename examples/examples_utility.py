# Copyright 2020, feelSpace GmbH, <info@feelspace.de>

"""This file contains a set of utility methods used by the different examples.

These utility functions are essentially designed for examples and tests run in a terminal and not necessarily adequate
for other programs.
"""
import logging
import sys
import serial
import pybelt

from serial.tools import list_ports

from pybelt.belt_controller import BeltController, BeltMode, BeltConnectionState
from pybelt.belt_scanner import BeltScanner


def belt_controller_log_to_stdout():
    """Configures the belt-controller logger to print all debug messages on `stdout`.
    """
    logger = pybelt.logger
    logger.setLevel(logging.DEBUG)
    sh = logging.StreamHandler(sys.stdout)
    sh_format = logging.Formatter('\033[92m %(levelname)s: %(message)s \033[0m')
    sh.setFormatter(sh_format)
    sh.setLevel(logging.DEBUG)
    logger.addHandler(sh)


def interactive_belt_connection(belt_controller):
    """Procedures to connect a belt using the terminal.

    The procedure asks for the interface to use (serial port or Bluetooth) and connects the belt-controller using it.

    :param BeltController belt_controller: The belt-controller to connect.
    """

    # List possible interfaces
    ports = serial.tools.list_ports.comports()
    if ports is None or len(ports) == 0:
        # Only Bluetooth available
        print("No serial port found (USB).")
        response = input("Connect the belt via Bluetooth? [y/n]")
        if response.lower() == "y":
            selected_interface = "Bluetooth"
        elif response.lower() == "n":
            return
        else:
            print("Unrecognized input.")
            return
    else:
        print("Which interface do you want to use? [1-{}]".format(len(ports)+1))
        for i, port in enumerate(ports):
            print("{}. {}".format((i + 1), port[0]))
        print("{}. Bluetooth.".format(len(ports)+1))
        interface_number = input()
        try:
            interface_number_int = int(interface_number)
        except ValueError:
            print("Unrecognized input.")
            return
        if interface_number_int < 1 or interface_number_int > len(ports)+1:
            print("Unrecognized input.")
            return
        if interface_number_int == len(ports)+1:
            selected_interface = "Bluetooth"
        else:
            selected_interface = ports[interface_number_int-1][0]

    # Use serial port or Bluetooth to connect belt
    if selected_interface == "Bluetooth":
        # Bluetooth scan and connect
        with pybelt.belt_scanner.create() as scanner:
            print("Start BLE scan.")
            belts = scanner.scan()
            print("BLE scan completed.")
        if len(belts) == 0:
            print("No belt found.")
            return
        if len(belts) > 1:
            print("Select the belt to connect.")
            for i, belt in enumerate(belts):
                advertised_uuid = "Unknown"
                if 'uuids' in belt.metadata:
                    for uuid in belt.metadata['uuids']:
                        advertised_uuid = uuid
                print("{}. {} - {} - Adv. UUID {}".format((i + 1), belt.name, belt.address, advertised_uuid))
            belt_selection = input("[1-{}]".format(len(belts)))
            try:
                belt_selection_int = int(belt_selection)
            except ValueError:
                print("Unrecognized input.")
                return
            print("Connect the belt.")
            belt_controller.connect(belts[belt_selection_int - 1])
        else:
            print("Connect the belt.")
            belt_controller.connect(belts[0])
    else:
        # Connect belt via serial port
        print("Connect the belt.")
        belt_controller.connect(selected_interface)


def belt_mode_to_string(mode) -> str:
    """ Returns the name of a belt mode.

    :param int mode: The belt mode
    :return: The name of the belt mode.
    """
    if mode == BeltMode.STANDBY:
        return "Standby"
    elif mode == BeltMode.WAIT:
        return "Wait"
    elif mode == BeltMode.COMPASS:
        return "Compass"
    elif mode == BeltMode.APP_MODE:
        return "App mode"
    elif mode == BeltMode.PAUSE:
        return "Pause"
    elif mode == BeltMode.CALIBRATION:
        return "Calibration"
    elif mode == BeltMode.CROSSING:
        return "Crossing"
    return "Unknown"


def belt_button_id_to_string(button_id) -> str:
    """ Returns the name of a belt button from its ID.

    :param int button_id: The ID of the button.
    :return: The name of the button.
    """
    if button_id == 1:
        return "Power"
    elif button_id == 2:
        return "Pause"
    elif button_id == 3:
        return "Compass"
    elif button_id == 4:
        return "Home"
    return "Unknown"


def connection_state_to_string(state) -> str:
    """ Return a string description of a connection state.

    :param state: The connection state.
    :return: The string description of the state.
    """
    if state == BeltConnectionState.DISCONNECTED:
        return "Disconnected"
    if state == BeltConnectionState.CONNECTING:
        return "Connecting"
    if state == BeltConnectionState.CONNECTED:
        return "Connected"
    if state == BeltConnectionState.DISCONNECTING:
        return "Disconnecting"
    return "Unknown"
