#! /usr/bin/env python
# encoding: utf-8

import pybelt
from examples.connect import interactive_belt_connect, setup_logger

from pybelt.belt_controller import BeltController, BeltConnectionState, BeltControllerDelegate, BeltMode


class Delegate(BeltControllerDelegate):

    def on_belt_mode_changed(self, belt_mode):
        print("Belt mode changed.")
        print_belt_mode(belt_mode)

    def on_belt_button_pressed(self, button_id, previous_mode, new_mode):
        print("Belt button pressed.")
        print_belt_mode(new_mode)


def print_belt_mode(mode):
    """
    Prints the belt mode.
    :param int mode: The belt mode.
    """
    if mode is None:
        print("Unknown mode.")
    elif mode == BeltMode.STANDBY:
        print("Belt mode is Standby.")
    elif mode == BeltMode.WAIT:
        print("Belt mode is Wait.")
    elif mode == BeltMode.COMPASS:
        print("Belt mode is Compass.")
    elif mode == BeltMode.APP_MODE:
        print("Belt mode is App mode.")
    elif mode == BeltMode.PAUSE:
        print("Belt mode is Pause.")
    elif mode == BeltMode.CALIBRATION:
        print("Belt mode is Calibration.")
    elif mode == BeltMode.CROSSING:
        print("Belt mode is Crossing.")


def main():
    setup_logger()

    # Interactive script to connect the belt
    belt_controller_delegate = Delegate()
    belt_controller = BeltController(belt_controller_delegate)
    interactive_belt_connect(belt_controller)
    if belt_controller.get_connection_state() != BeltConnectionState.CONNECTED:
        print("Connection failed.")
        return 0

    while belt_controller.get_connection_state() == BeltConnectionState.CONNECTED:
        print("Select the mode to set:")
        print("1. Wait")
        print("2. Compass")
        print("3. App mode")
        print("4. Pause")
        print("5. Crossing")
        print("Q to quit.")
        action = input()
        try:
            action_int = int(action)
            if action_int == 1:
                belt_controller.set_belt_mode(BeltMode.WAIT)
            elif action_int == 2:
                belt_controller.set_belt_mode(BeltMode.COMPASS)
            elif action_int == 3:
                belt_controller.set_belt_mode(BeltMode.APP_MODE)
            elif action_int == 4:
                belt_controller.set_belt_mode(BeltMode.PAUSE)
            elif action_int == 5:
                belt_controller.set_belt_mode(BeltMode.CROSSING)
        except ValueError:
            if action.lower() == "q" or action.lower() == "quit":
                belt_controller.disconnect_belt()
            else:
                print("Unrecognized input.")

    return 0


if __name__ == "__main__":
    main()