#! /usr/bin/env python
# encoding: utf-8
from pybelt.examples_utility import belt_controller_log_to_stdout, interactive_belt_connection
from pybelt.belt_controller import BeltController, BeltConnectionState, BeltControllerDelegate, BeltMode, \
    BeltOrientationType, BeltVibrationTimerOption


class Delegate(BeltControllerDelegate):
    # Belt controller delegate
    pass


def main():
    belt_controller_log_to_stdout()

    # Interactive script to connect the belt
    belt_controller_delegate = Delegate()
    belt_controller = BeltController(belt_controller_delegate)
    interactive_belt_connection(belt_controller)
    if belt_controller.get_connection_state() != BeltConnectionState.CONNECTED:
        print("Connection failed.")
        return 0

    # Change belt mode to APP mode
    belt_controller.set_belt_mode(BeltMode.APP_MODE)

    while belt_controller.get_connection_state() == BeltConnectionState.CONNECTED:
        print("Q to quit.")
        print("Motor index (0-15)?")

        action = input()
        try:
            action_int = int(action)
            motor_index = (action_int % 16)
            if motor_index < 0:
                action_int += 16
            belt_controller.send_pulse_command(
                channel_index=1,
                orientation_type=BeltOrientationType.MOTOR_INDEX,
                orientation=motor_index,
                intensity=None,
                on_duration_ms=250,
                pulse_period=1000,
                pulse_iterations=1,
                series_period=1000,
                series_iterations=0,
                timer_option=BeltVibrationTimerOption.RESET_TIMER,
                exclusive_channel=False,
                clear_other_channels=False
            )

        except ValueError:
            if action.lower() == "q" or action.lower() == "quit":
                belt_controller.disconnect_belt()
            else:
                print("Unrecognized input.")

    return 0


if __name__ == "__main__":
    main()