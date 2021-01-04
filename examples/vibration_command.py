#! /usr/bin/env python
# encoding: utf-8

import pybelt
from examples.connect import interactive_belt_connect, setup_logger

from pybelt.belt_controller import BeltController, BeltConnectionState, BeltControllerDelegate, BeltMode, \
    BeltVibrationPattern, BeltOrientationType


class Delegate(BeltControllerDelegate):
    # Belt controller delegate
    pass


def main():
    setup_logger()

    # Interactive script to connect the belt
    belt_controller_delegate = Delegate()
    belt_controller = BeltController(belt_controller_delegate)
    interactive_belt_connect(belt_controller)
    if belt_controller.get_connection_state() != BeltConnectionState.CONNECTED:
        print("Connection failed.")
        return 0

    # Change belt mode to APP mode
    belt_controller.set_belt_mode(BeltMode.APP_MODE)

    while belt_controller.get_connection_state() == BeltConnectionState.CONNECTED:
        print("Q to quit.")
        print("0: Stop vibration.")
        print("1: Start vibration on the right (channel 0).")
        print("2: Start vibration toward West (channel 1).")
        print("3: Start vibration on the left for 3 seconds (channel 2).")
        action = input()
        try:
            action_int = int(action)
            if action_int == 0:
                belt_controller.stop_vibration()
            elif action_int == 1:
                belt_controller.vibrate_at_angle(90, channel_index=0)
            elif action_int == 2:
                belt_controller.vibrate_at_magnetic_bearing(270, channel_index=1)
            elif action_int == 3:
                belt_controller.send_vibration_command(
                    channel_index=2,
                    pattern=BeltVibrationPattern.CONTINUOUS,
                    intensity=None,
                    orientation_type=BeltOrientationType.ANGLE,
                    orientation=270,
                    pattern_iterations=1,
                    pattern_period=3000,
                    pattern_start_time=0,
                    exclusive_channel=False,
                    clear_other_channels=False
                )
            else:
                print("Unrecognized input.")
        except ValueError:
            if action.lower() == "q" or action.lower() == "quit":
                belt_controller.disconnect_belt()
            else:
                print("Unrecognized input.")

    return 0


if __name__ == "__main__":
    main()