#! /usr/bin/env python
# encoding: utf-8
import logging
import sys
from threading import Event

import pybelt
from examples.connect import interactive_belt_connect

from pybelt.belt_controller import BeltController, BeltConnectionState, BeltControllerDelegate

# Event to stop the script
button_pressed_event = Event()


class Delegate(BeltControllerDelegate):

    def on_belt_battery_notified(self, charge_level, extra):
        print("\rBelt battery {}%            ".format(round(charge_level, 2)), end="")

    def on_belt_button_pressed(self, button_id, previous_mode, new_mode):
        button_pressed_event.set()


def main():
    # Config logger to output pybelt debug messages on console
    logger = pybelt.logger
    logger.setLevel(logging.DEBUG)
    sh = logging.StreamHandler(sys.stdout)
    sh_format = logging.Formatter('\033[92m %(levelname)s: %(message)s \033[0m')
    sh.setFormatter(sh_format)
    sh.setLevel(logging.DEBUG)
    logger.addHandler(sh)

    # Interactive script to connect the belt
    belt_controller_delegate = Delegate()
    belt_controller = BeltController(belt_controller_delegate)
    interactive_belt_connect(belt_controller)
    if belt_controller.get_connection_state() != BeltConnectionState.CONNECTED:
        print("Connection failed.")
        return 0

    # Start battery notification (should already be started during handshake)
    belt_controller.set_power_status_notifications(True)

    print("Press a button on the belt to quit.")
    while belt_controller.get_connection_state() == BeltConnectionState.CONNECTED and not button_pressed_event.is_set():
        button_pressed_event.wait(timeout=0.2)
    belt_controller.disconnect_belt()
    return 0


if __name__ == "__main__":
    main()
