#! /usr/bin/env python
# encoding: utf-8
from pybelt.examples_utility import belt_controller_log_to_stdout, interactive_belt_connection
from pybelt.belt_controller import BeltController, BeltConnectionState, BeltControllerDelegate, BeltMode


class Delegate(BeltControllerDelegate):

    def on_pairing_requirement_notified(self, pairing_required):
        if pairing_required:
            print("Pairing set as required.")
        else:
            print("Pairing set as not required.")


def main():
    belt_controller_log_to_stdout()

    # Interactive script to connect the belt
    belt_controller_delegate = Delegate()
    belt_controller = BeltController(belt_controller_delegate)
    interactive_belt_connection(belt_controller)
    if belt_controller.get_connection_state() != BeltConnectionState.CONNECTED:
        print("Connection failed.")
        return 0

    while belt_controller.get_connection_state() == BeltConnectionState.CONNECTED:
        print("Select the setting:")
        print("1. Pairing required (temporary)")
        print("2. Pairing not required (temporary)")
        print("3. Pairing required (saved)")
        print("4. Pairing not required (saved)")
        print("Q to quit.")
        action = input()
        try:
            action_int = int(action)
            if action_int == 1:
                belt_controller.set_pairing_requirement(True, False)
            elif action_int == 2:
                belt_controller.set_pairing_requirement(False, False)
            elif action_int == 3:
                belt_controller.set_pairing_requirement(True, True)
            elif action_int == 4:
                belt_controller.set_pairing_requirement(False, True)
        except ValueError:
            if action.lower() == "q" or action.lower() == "quit":
                belt_controller.disconnect_belt()
            else:
                print("Unrecognized input.")

    return 0


if __name__ == "__main__":
    main()
