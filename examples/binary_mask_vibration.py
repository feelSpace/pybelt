#! /usr/bin/env python
# encoding: utf-8
from pybelt.examples_utility import belt_controller_log_to_stdout, interactive_belt_connection
from pybelt.belt_controller import BeltController, BeltConnectionState, BeltControllerDelegate, BeltMode, \
    BeltOrientationType, BeltVibrationTimerOption, BeltVibrationPattern


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
    belt_controller.set_belt_mode(BeltMode.APP_MODE, wait_ack=True)

    # Stop orientation warning signal
    belt_controller.set_inaccurate_orientation_signal_state(enable_in_app=False, save_on_belt=False,
                                                            enable_in_compass=False, wait_ack=True)
    print("Orientation inaccurate signal has been disabled temporarily.\n")

    while belt_controller.get_connection_state() == BeltConnectionState.CONNECTED:
        print("Q to quit.")
        print("0: Stop vibration.")
        print("1: Three pulses on three motors (front, left and right).")
        print("2: One second vibration on two motors (front-left and front-right).")

        action = input()
        try:
            action_int = int(action)
            if action_int == 0:
                belt_controller.stop_vibration()
            elif action_int == 1:
                # Three pulses on three motors (front, left and right):
                # Front motor: index  0, binary mask (= 0b1 << 0)  = 0b00000000_00000001
                # Left motor:  index 12, binary mask (= 0b1 << 12) = 0b00010000_00000000
                # Right motor: index  4, binary mask (= 0b1 << 4)  = 0b00000000_00010000
                #                            Resulting binary mask = 0b00010000000010001
                belt_controller.send_pulse_command(
                    channel_index=0,
                    orientation_type=BeltOrientationType.BINARY_MASK,
                    orientation=(0b1 << 0) | (0b1 << 12) | (0b1 << 4),
                    intensity=None,
                    on_duration_ms=150,
                    pulse_period=500,
                    pulse_iterations=3,
                    series_period=1500,
                    series_iterations=1,
                    timer_option=BeltVibrationTimerOption.RESET_TIMER,
                    exclusive_channel=False,
                    clear_other_channels=False
                )
            elif action_int == 2:
                # One second vibration on two motors (front-left and front-right)
                # Front-left motor:  index 14, binary mask (= 0b1 << 14) = 0b01000000_00000000
                # Front-right motor: index  2, binary mask (= 0b1 << 2)  = 0b00000000_00000100
                #                                  Resulting binary mask = 0b01000000000000100
                belt_controller.send_vibration_command(
                    channel_index=0,
                    pattern=BeltVibrationPattern.CONTINUOUS,
                    intensity=None,
                    orientation_type=BeltOrientationType.BINARY_MASK,
                    orientation=(0b1 << 14) | (0b1 << 2),
                    pattern_iterations=1,
                    pattern_period=1000,
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