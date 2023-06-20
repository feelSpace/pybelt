#! /usr/bin/env python
# encoding: utf-8
import time
from datetime import datetime
from datetime import timedelta
from threading import Event, Lock

from examples.examples_utility import belt_controller_log_to_stdout, interactive_belt_connection
from pybelt.belt_controller import BeltController, BeltConnectionState, BeltControllerDelegate

# Event to stop the script
button_pressed_event = Event()

# Belt orientation
orientation_lock = Lock()  # Lock to read and write the heading and period (only necessary for BLE interface)
belt_heading: int = -1  # Last known belt heading value
belt_orientation_update_period = timedelta()  # Period between the last two orientation updates


class Delegate(BeltControllerDelegate):

    def __init__(self):
        # __init__ is only used for the orientation notification period
        self._last_orientation_update_time = datetime.now()  # Time of the last heading update

    def on_belt_orientation_notified(self, heading, is_orientation_accurate, extra):
        global belt_heading
        global belt_orientation_update_period
        with orientation_lock:
            belt_heading = heading
            # Below code is only for measuring notification period
            now = datetime.now()
            belt_orientation_update_period = now - self._last_orientation_update_time
            self._last_orientation_update_time = now

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

    # Change orientation notification period
    belt_controller.set_orientation_notifications(True)

    print("Press a button on the belt to quit.")
    while belt_controller.get_connection_state() == BeltConnectionState.CONNECTED and not button_pressed_event.is_set():
        # Delay for terminal display (not necessary if other processing)
        time.sleep(0.005)
        # Retrieve orientation with lock
        with orientation_lock:
            heading = belt_heading
            notification_period = belt_orientation_update_period.total_seconds()
        # Process orientation
        print("\rBelt heading: {}°\t (period: {:.3f}s)            ".format(heading, notification_period), end="")

    belt_controller.set_orientation_notifications(False)
    belt_controller.disconnect_belt()
    return 0


if __name__ == "__main__":
    main()
