#! /usr/bin/env python
# encoding: utf-8

import pybelt
from examples.connect import interactive_belt_connect, setup_logger

from pybelt.belt_controller import BeltController, BeltConnectionState, BeltControllerDelegate, BeltMode


class Delegate(BeltControllerDelegate):

    def dummy(self):
        # TODO
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

    # 0 -> Stop vibration
    # 1 -> Three short pulses on the right (90°, channel 0)
    # 2 -> Continuous long pulses toward West (270°, channel 1)
    # 3 -> Two times two pulses on front (0°, channel 2)

    while belt_controller.get_connection_state() == BeltConnectionState.CONNECTED:
        print("Q to quit.")
        action = input()
        try:
            action_int = int(action)
            if action_int == 1:
                # TODO
                pass
            elif action_int == 2:
                # TODO
                pass
        except ValueError:
            if action.lower() == "q" or action.lower() == "quit":
                belt_controller.disconnect_belt()
            else:
                print("Unrecognized input.")

    return 0


if __name__ == "__main__":
    main()