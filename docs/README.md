# pyBelt documentation

## Content

...

## Copyright and license notice

Copyright 2020, feelSpace GmbH.

Licensed under the Apache License, Version 2.0: http://www.apache.org/licenses/LICENSE-2.0

**Note on using feelSpace Trademarks and Copyrights:**

*Attribution:* You must give appropriate credit to feelSpace GmbH when you use feelSpace products in a publicly disclosed derived work. For instance, you must reference feelSpace GmbH in publications, conferences or seminars when a feelSpace product has been used in the presented work.

*Endorsement or Sponsorship:* You may not use feelSpace name, feelSpace products’ name, and logos in a way that suggests an affiliation or endorsement by feelSpace GmbH of your derived work, except if it was explicitly communicated by feelSpace GmbH.


## Installation

To install pyBelt:
```
pip install pyBelt
```

### Requirement

PyBelt requires python 3.3 or higher (due to the requirements of [bleak](https://github.com/hbldh/bleak) the library used for Bluetooth communication).

### Known issue with python 3.9 on Windows

Installation via pip seams to cause problem on Window with python 3.9 because of an incompatibility in the dependencies of [bleak](https://github.com/hbldh/bleak) (the Bluetooth communication library). Bleak uses [pythonet](http://pythonnet.github.io/), on Windows, which is not yet compatible with python 3.9.

## Belt pairing (only for Bluetooth connection)

**Important:** The belt support Bluetooth Low-Energy (BLE), i.e. Bluetooth 4, and not Bluetooth classic. Verify that your computer has a Bluetooth Low-Energy adapter, if not you can add a Bluetooth Low-Energy USB-dongle.

When using the Bluetooth connection, the belt must be paired with the computer running the application. The pairing must be made by the OS and is NOT managed by the pyBelt library (nor by bleak). With the USB connection (to be used only for development or for applications where the user is seated) there is no pairing.

**Note:** Pairing is required only once per system. When the belt is pairing within the OS, you can use pyBelt and establish a connection with the belt without restarting the pairing procedure.

**Note:** Even if the belt is not paired and not in pairing mode, it is still visible when a scan procedure is started. If the connection fails with a belt, please verify that the belt is available in the list of paired devices from the settings of the OS.

### Pairing on Windows

- Start the pairing mode of the belt by pressing the Home button on the belt for at least 5 seconds until a fast vibration pulse start. The pairing mode is active for 60 seconds.
- In Windows 10, from the Bluetooth parameters, select “Adds a Bluetooth peripheral”.
- When the device “naviguertel” appears in the list of detected devices, click on it to pair it. The belt should stop its pairing mode and the “naviguertel” should appear in the list of paired devices in Windows.
- If the pairing fails, please verify that the belt is in pairing mode and restart the procedure to add a Bluetooth peripheral in Windows.

### Pairing on Linux

- Start the pairing mode of the belt by pressing the Home button on the belt for at least 5 seconds until a fast vibration pulse start. The pairing mode is active for 60 seconds.
- Open the Bluetooth settings and scan for new deives.
- When the device “naviguertel” appears in the list of detected devices, click on it to pair it. The belt should stop its pairing mode and the “naviguertel” should appear in the list of paired devices in the Bluetooth settings.
- If the pairing fails, please verify that the belt is in pairing mode and restart the procedure to add a Bluetooth peripheral in Windows.

## Belt connection

### Connection via USB

**Important:** The USB connection is only for development and possibly for applications where the user is seated and does not move. The USB connector may be damaged if the cable is not maintained straight.

When a belt is connected to a USB port, it should appear as a serial communication port in your OS. Serial ports are labeled `COM#` in Windows 10 and `/dev/ttyUSB#` in Linux.

To establish a connection using USB within pyBelt you must first retrieve the port name then call the `connect()` method of a `BeltController` instance.

#### Retrieving the list of serial ports
See [examples/list_serial.py]( https://github.com/feelSpace/pybelt/blob/main/examples/list_serial.py).
```
# Retrieve the list of serial COM ports
ports = serial.tools.list_ports.comports()
for comm_port in ports:
    print("Serial port: {}".format(comm_port[0]))
```

#### Establishing a connection
See [examples/connect.py]( https://github.com/feelSpace/pybelt/blob/main/examples/connect.py).
```
belt_controller = BeltController()
belt_controller.connect('COM3') # Port name only for illustration
```
