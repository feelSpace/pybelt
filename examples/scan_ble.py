#! /usr/bin/env python
# encoding: utf-8

import pybelt
from examples.connect import setup_logger
from pybelt.belt_scanner import BeltScanner


def main():
    setup_logger()

    # Scan
    with pybelt.belt_scanner.create() as scanner:
        print("Start scan.")
        belts = scanner.scan()
        print("Scan completed.")

    # Alternative:
    # scanner = BeltScanner()
    # belts = scanner.scan()
    # scanner.close()

    # Output
    if len(belts) == 0:
        print("No belt found.")
    else:
        if len(belts) == 1:
            print("One belt found.")
        else:
            print("{} belts found.".format(len(belts)))
        for belt in belts:
            print("Address: {}".format(belt.address))


if __name__ == "__main__":
    main()
