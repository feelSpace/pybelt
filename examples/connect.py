#! /usr/bin/env python
# encoding: utf-8

"""This example shows how to use the `BeltController` class to connect a belt.
"""

from pybelt.examples_utility import belt_controller_log_to_stdout, interactive_belt_connection
from pybelt.belt_controller import BeltController, BeltConnectionState


def main():
    belt_controller_log_to_stdout()

    # Interactive script to connect the belt
    belt_controller = BeltController()
    interactive_belt_connection(belt_controller)
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
