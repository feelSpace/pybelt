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
        print("0: Stop vibration.")
        print("1: Start three short pulses on the right (channel 0).")
        print("2: Start unlimited long pulses toward West (channel 1).")
        print("3: Start two series of two pulses on front (channel 2).")

        print("4: Standard crossing.")
        print("5: Long pulses, 1sec - 1sec.")
        print("6: Long pulses, 2sec - 1sec.")
        print("7: Short pulses, 0.25sec - 0.25sec.")
        print("8: Very short pulses, 0.1sec - 0.1sec.")

        action = input()
        try:
            action_int = int(action)
            if action_int == 0:
                belt_controller.stop_vibration()
            elif action_int == 1:
                belt_controller.send_pulse_command(
                    channel_index=0,
                    orientation_type=BeltOrientationType.ANGLE,
                    orientation=90,
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
                belt_controller.send_pulse_command(
                    channel_index=1,
                    orientation_type=BeltOrientationType.MAGNETIC_BEARING,
                    orientation=270,
                    intensity=None,
                    on_duration_ms=300,
                    pulse_period=1000,
                    pulse_iterations=1,
                    series_period=1000,
                    series_iterations=None,
                    timer_option=BeltVibrationTimerOption.RESET_TIMER,
                    exclusive_channel=False,
                    clear_other_channels=False
                )
            elif action_int == 3:
                belt_controller.send_pulse_command(
                    channel_index=2,
                    orientation_type=BeltOrientationType.ANGLE,
                    orientation=0,
                    intensity=None,
                    on_duration_ms=150,
                    pulse_period=250,
                    pulse_iterations=2,
                    series_period=1000,
                    series_iterations=2,
                    timer_option=BeltVibrationTimerOption.RESET_TIMER,
                    exclusive_channel=False,
                    clear_other_channels=False
                )

            elif action_int == 4:
                belt_controller.send_pulse_command(
                    channel_index=1,
                    orientation_type=BeltOrientationType.MAGNETIC_BEARING,
                    orientation=270,
                    intensity=None,
                    on_duration_ms=500,
                    pulse_period=750,
                    pulse_iterations=1,
                    series_period=750,
                    series_iterations=None,
                    timer_option=BeltVibrationTimerOption.RESET_TIMER,
                    exclusive_channel=False,
                    clear_other_channels=False
                )
            elif action_int == 5:
                belt_controller.send_pulse_command(
                    channel_index=1,
                    orientation_type=BeltOrientationType.MAGNETIC_BEARING,
                    orientation=270,
                    intensity=None,
                    on_duration_ms=1000,
                    pulse_period=2000,
                    pulse_iterations=1,
                    series_period=2000,
                    series_iterations=None,
                    timer_option=BeltVibrationTimerOption.RESET_TIMER,
                    exclusive_channel=False,
                    clear_other_channels=False
                )
            elif action_int == 6:
                belt_controller.send_pulse_command(
                    channel_index=1,
                    orientation_type=BeltOrientationType.MAGNETIC_BEARING,
                    orientation=270,
                    intensity=None,
                    on_duration_ms=2000,
                    pulse_period=3000,
                    pulse_iterations=1,
                    series_period=3000,
                    series_iterations=None,
                    timer_option=BeltVibrationTimerOption.RESET_TIMER,
                    exclusive_channel=False,
                    clear_other_channels=False
                )
            elif action_int == 7:
                belt_controller.send_pulse_command(
                    channel_index=1,
                    orientation_type=BeltOrientationType.MAGNETIC_BEARING,
                    orientation=270,
                    intensity=None,
                    on_duration_ms=250,
                    pulse_period=500,
                    pulse_iterations=1,
                    series_period=500,
                    series_iterations=None,
                    timer_option=BeltVibrationTimerOption.RESET_TIMER,
                    exclusive_channel=False,
                    clear_other_channels=False
                )
            elif action_int == 8:
                belt_controller.send_pulse_command(
                    channel_index=1,
                    orientation_type=BeltOrientationType.MAGNETIC_BEARING,
                    orientation=270,
                    intensity=None,
                    on_duration_ms=100,
                    pulse_period=200,
                    pulse_iterations=1,
                    series_period=200,
                    series_iterations=None,
                    timer_option=BeltVibrationTimerOption.RESET_TIMER,
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