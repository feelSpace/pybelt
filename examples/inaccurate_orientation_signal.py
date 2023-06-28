#! /usr/bin/env python
# encoding: utf-8
from examples.examples_utility import belt_controller_log_to_stdout, interactive_belt_connection
from pybelt.belt_controller import BeltController, BeltConnectionState, BeltControllerDelegate


class Delegate(BeltControllerDelegate):

    def on_inaccurate_orientation_signal_state_notified(self, signal_enabled_in_app_mode,
                                                        signal_enabled_in_compass_mode):
        if signal_enabled_in_app_mode:
            print("Inaccurate orientation signal enabled in application mode.")
        else:
            print("Inaccurate orientation signal disabled in application mode.")


def main():
    belt_controller_log_to_stdout()

    # Interactive script to connect the belt
    belt_controller_delegate = Delegate()
    belt_controller = BeltController(belt_controller_delegate)
    interactive_belt_connection(belt_controller)
    if belt_controller.get_connection_state() != BeltConnectionState.CONNECTED:
        print("Connection failed.")
        return 0

    # Retrieve inaccurate signal state
    signal_state = belt_controller.get_inaccurate_orientation_signal_state()
    if signal_state is not None:
        if signal_state[0]:
            print("Inaccurate orientation signal enabled in application mode.")
        else:
            print("Inaccurate orientation signal disabled in application mode.")
    while belt_controller.get_connection_state() == BeltConnectionState.CONNECTED:
        print("Select the setting:")
        print("1. Enable inaccurate orientation signal (temporary)")
        print("2. Disable inaccurate orientation signal (temporary)")
        print("3. Enable inaccurate orientation signal (saved)")
        print("4. Disable inaccurate orientation signal (saved)")
        print("Q to quit.")
        action = input()
        try:
            action_int = int(action)
            if action_int == 1:
                belt_controller.set_inaccurate_orientation_signal_state(True, False)
            elif action_int == 2:
                belt_controller.set_inaccurate_orientation_signal_state(False, False)
            elif action_int == 3:
                belt_controller.set_inaccurate_orientation_signal_state(True, True)
            elif action_int == 4:
                belt_controller.set_inaccurate_orientation_signal_state(False, True)
        except ValueError:
            if action.lower() == "q" or action.lower() == "quit":
                belt_controller.disconnect_belt()
            else:
                print("Unrecognized input.")

    return 0


if __name__ == "__main__":
    main()
