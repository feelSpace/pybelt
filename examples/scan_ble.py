#! /usr/bin/env python
# encoding: utf-8
import logging
import sys

import pybelt
from pybelt.belt_scanner import BeltScanner


def main():

    # Config logger to output pybelt debug messages on console
    logger = pybelt.logger
    logger.setLevel(logging.DEBUG)
    sh = logging.StreamHandler(sys.stdout)
    sh_format = logging.Formatter('\033[92m %(levelname)s: %(message)s \033[0m')
    sh.setFormatter(sh_format)
    sh.setLevel(logging.DEBUG)
    logger.addHandler(sh)

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
