#! /usr/bin/env python
# encoding: utf-8
import pybelt
from pybelt.examples_utility import belt_controller_log_to_stdout
from pybelt.belt_controller import BeltController, BeltConnectionState
from pybelt.belt_scanner import BeltScanner


def main():
    belt_controller_log_to_stdout()

    # Notice
    print("Note: Before establishing simultaneous connections, you must either: ")
    print("1) deactivate the pairing of the belt, ")
    print("or 2) give a different name to each belt and pair each belt in your OS settings.")

    # Scan for available belts
    scan_belt = True
    belts = []
    while scan_belt:
        with pybelt.belt_scanner.create() as scanner:
            print("Start BLE scan.")
            belts = scanner.scan()
            print("BLE scan completed.")
        if len(belts) == 0:
            scan_again = input("No belt found. Scan again or Quit? [s, q]")
            if scan_again.lower() != "s":
                return 0
        else:
            # Print list of belts
            if len(belts) == 1:
                print("1 belt found:")
            else:
                print("{} belts found:".format(len(belts)))
            for i, belt in enumerate(belts):
                print("{}. {} - {}".format((i + 1), belt.name, belt.address))
            scan_again = input("Connect, Scan again, or Quit? [c, s, q]")
            if scan_again.lower() == "s":
                belts = []
            elif scan_again.lower() == "c":
                scan_belt = False
            else:
                return 0

    # Connect to all available belts
    belt_controllers = []
    for i, belt in enumerate(belts):
        print("Connect belt: {}. {} - {}".format((i + 1), belt.name, belt.address))
        belt_controller = BeltController()
        belt_controller.connect(belts[i])
        belt_controllers.append(belt_controller)
        if belt_controller.get_connection_state() == BeltConnectionState.CONNECTED:
            print("Belt connected.")
        else:
            print("Belt connection failed.")
    print("All connection attempts done.")

    # Summary
    connected_belt_count = 0
    for belt_controller in belt_controllers:
        if belt_controller.get_connection_state() == BeltConnectionState.CONNECTED:
            connected_belt_count += 1
    print("Belt connected {}/{}".format(connected_belt_count, len(belt_controllers)))
    input("Press enter to disconnect and quit.")

    # Disconnect all belts
    for belt_controller in belt_controllers:
        belt_controller.disconnect_belt()

    return 0


if __name__ == "__main__":
    main()
