#! /usr/bin/env python
# encoding: utf-8
import logging
import sys

import pybelt
from examples.connect import interactive_belt_connect

from pybelt.belt_controller import BeltController, BeltConnectionState, BeltControllerDelegate, BeltMode


class Delegate(BeltControllerDelegate):

    def dummy(self):
        # TODO
        pass


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