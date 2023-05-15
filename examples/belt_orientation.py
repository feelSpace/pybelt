#! /usr/bin/env python
# encoding: utf-8
from threading import Event

from examples.examples_utility import belt_controller_log_to_stdout, interactive_belt_connection
from pybelt.belt_controller import BeltController, BeltConnectionState, BeltControllerDelegate

# Event to stop the script
button_pressed_event = Event()


class Delegate(BeltControllerDelegate):

    def on_belt_orientation_notified(self, heading, is_orientation_accurate, extra):
        print("\rBelt heading {}°, accurate: {}, (y: {}, r: {}, p: {})            ".format(
            heading, is_orientation_accurate, extra[2], extra[3], extra[4]), end="")

    def on_belt_button_pressed(self, button_id, previous_mode, new_mode):
        button_pressed_event.set()


def main():
    belt_controller_log_to_stdout()

    # Interactive script to connect the belt
    belt_controller_delegate = Delegate()
    belt_controller = BeltController(belt_controller_delegate)
    interactive_belt_connection(belt_controller)
    if belt_controller.get_connection_state() != BeltConnectionState.CONNECTED:
        print("Connection failed.")
        return 0

    # Start orientation notification (should already be started during handshake)
    belt_controller.set_orientation_notifications(True)

    print("Press a button on the belt to quit.")
    while belt_controller.get_connection_state() == BeltConnectionState.CONNECTED and not button_pressed_event.is_set():
        button_pressed_event.wait(timeout=0.2)
    belt_controller.disconnect_belt()
    return 0


if __name__ == "__main__":
    main()
