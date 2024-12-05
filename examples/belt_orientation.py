#! /usr/bin/env python
# encoding: utf-8
import time
from threading import Event

from pybelt.examples_utility import belt_controller_log_to_stdout, interactive_belt_connection
from pybelt.belt_controller import BeltController, BeltConnectionState, BeltControllerDelegate

# Event to stop the script
button_pressed_event = Event()


class Delegate(BeltControllerDelegate):

    def __init__(self):
        self.heading = -1
        self.period = -1.0
        self._last_orientation_notification_time = -1.0

    def on_belt_orientation_notified(self, heading, is_orientation_accurate, extra):
        self.heading = heading
        current_time = time.time()
        if self._last_orientation_notification_time > 0.0 :
            self.period = current_time - self._last_orientation_notification_time
        print("\rBelt heading: {}°\t (period: {:.3f}s)            ".format(
            self.heading, self.period), end="")
        self._last_orientation_notification_time = current_time

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

    # Activate orientation notifications (this is already done in handshake)
    # > belt_controller.set_orientation_notifications(True)

    print("Press a button on the belt to quit.")
    # Loop to allows for terminal display
    while belt_controller.get_connection_state() == BeltConnectionState.CONNECTED and not button_pressed_event.is_set():
        button_pressed_event.wait(timeout=0.2)

    # Deactivate orientation notification is not necessary
    # > belt_controller.set_orientation_notifications(False)

    belt_controller.disconnect_belt()
    return 0


if __name__ == "__main__":
    main()
