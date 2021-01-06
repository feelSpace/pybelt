# pyBelt documentation

## Content

* [Copyright and license notice](#copyright-and-license-notice)
* [Installation](#installation)
* [Belt pairing (only Bluetooth)](belt-pairing-only-for-bluetooth-connection)
* [Belt connection](belt-connection)
* [Control of the belt mode](control-of-the-belt-mode)
* [Control of the vibration](control-of-the-vibration)
* [Orientation of the belt](orientation-of-the-belt)
* [Battery level of the belt](battery-level-of-the-belt)

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

## Belt pairing (only Bluetooth)

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
```python
import serial

# Retrieve the list of serial COM ports
ports = serial.tools.list_ports.comports()
for comm_port in ports:
    print("Serial port: {}".format(comm_port[0]))
```

#### Establishing a connection
See [examples/connect.py]( https://github.com/feelSpace/pybelt/blob/main/examples/connect.py).
```python
from pybelt.belt_controller import *

belt_controller = BeltController()
belt_controller.connect('COM3') # Port name only for illustration
```

### Connection via Bluetooth

**Important:** The belt support Bluetooth Low-Energy (BLE), i.e. Bluetooth 4, and not Bluetooth classic. Verify that your computer has a Bluetooth Low-Energy adapter, if not, you can buy a Bluetooth Low-Energy USB-dongle.

To establish a connection via Bluetooth within pyBelt you must first scan for available devices, i.e. retrieve the list of BLE devices available. Then call the `connect()` method of a `BeltController` instance using the belt obtain during scan.

#### Scanning
See [examples/scan_ble.py]( https://github.com/feelSpace/pybelt/blob/main/examples/scan_ble.py).
```python
from pybelt.belt_scanner import *

# Retrieve the list of available belts
with pybelt.belt_scanner.create() as scanner:
        belts = scanner.scan()
for belt in belts:
    print("Belt BLE address: {}".format(belt.address))
```

#### Connecting

See [examples/connect.py]( https://github.com/feelSpace/pybelt/blob/main/examples/connect.py).
```python
from pybelt.belt_scanner import *
from pybelt.belt_controller import *

belt_controller = BeltController()
# Retrieve the list of available belts
with pybelt.belt_scanner.create() as scanner:
        belts = scanner.scan()
# Connect to the first belt found
if len(belts) > 0:
    belt_controller.connect(belts[0])
```

## Control of the belt mode

The belt has seven “modes” of operation that are controlled by button press or changed by a connected device. 

| Mode | Description |
| --- | --- |
| *standby* | In standby, all components of the belt, including Bluetooth, are switched-off. The belt only reacts to a long press on the power button that starts the belt and put it in wait mode. Since Bluetooth connection is not possible in standby mode, the Bluetooth connection is closed after a notification of the standby mode. |
| *wait* | In wait mode, the belt waits for a user input, either a button-press or a command from a connected device. A periodic vibration signal indicates that the belt is active. This wait signal is a single pulse when no device is connected, a double pulse when a device is connected, and a succession of short pulses when the belt is in pairing mode. |
| *compass* | In compass mode, the belt vibrates towards magnetic North. From the wait and app modes, the compass mode is obtained by a press on the compass button of the belt. |
| *crossing* | In crossing mode, the belt vibrates towards an initial heading direction. From the wait and app modes, the crossing mode is obtained by a double press on the compass button of the belt. |
| *app-mode* | The app-mode is the mode in which the vibration is controlled by the connected device. The app-mode is only accessible when the device is connected. If the device is unexpectedly disconnected in app-mode, the belt switches automatically to the wait mode. |
| *pause* | In pause mode, the vibration is stopped. From the wait, compass and app modes, the pause mode is obtained by a press on the pause button. Another press on the pause button in pause mode returns to the previous mode. In pause mode, the user can change the (default) vibration intensity by pressing the home button (increase intensity) or compass button (decrease intensity). |
| *calibration* | The calibration mode is used for the calibration procedure of the belt. |

An enumeration of belt mode values is available in the class `BeltMode`.
When a belt is connected, the mode can be retrieved using the method `get_belt_mode()` of the `BeltController`.
```python
mode = belt_controller.get_belt_mode()
```

To change the mode call `set_belt_mode()` method of the `BeltController`.
```python
# Change the mode to app-mode
mode = belt_controller.set_belt_mode(BeltMode.APP_MODE)
```

To listen to mode changes you must implement the `BeltControllerDelegate` interface which is given as parameter to the `BeltController` constructor. The method `on_belt_mode_changed()` of the `BeltControllerDelegate` interface is called to inform that the application changed the belt mode. The method `on_belt_button_pressed()` of the  `BeltControllerDelegate` interface also inform about mode change, but when a button of the belt has been pressed.

See [examples/belt_mode.py](https://github.com/feelSpace/pybelt/blob/main/examples/belt_mode.py).

## Control of the vibration

To control the vibration of the belt, the mode must be set to app-mode. In the other modes, only vibration commands on channel index 1 and with limited duration are allowed.

The belt has 6 channels to manage simultaneous vibrations.

To start continuous vibrations, two methods are available:
- `vibrate_at_angle()` to start a vibration in a given orientation relative to the user itself,
- `vibrate_at_magnetic_bearing()` to start a vibration in a given orientation relative to magnetic North.
```python
# Start a vibration on the right
belt_controller.vibrate_at_angle(90, channel_index=0)
# Start a vibration toward West
belt_controller.vibrate_at_magnetic_bearing(270, channel_index=1)
```
For “fine-tuned” vibration signals, two methods are available:
- `send_vibration_command()` to configure the vibration on a channel,
- ` send_pulse_command()` to configure a series of vibration pulses on a channel.

See [examples/vibration_command.py](https://github.com/feelSpace/pybelt/blob/main/examples/vibration_command.py) and [examples/pulse_command.py](https://github.com/feelSpace/pybelt/blob/main/examples/pulse_command.py).

## Orientation of the belt

The belt regularly notifies the application of its orientation. To listen to orientation notifications, you must implement the `BeltControllerDelegate` interface. The method `on_belt_orientation_notified()` is called when an orientation notification is received.

See [examples/belt_orientation.py](https://github.com/feelSpace/pybelt/blob/main/examples/belt_orientation.py).

## Battery level of the belt

The belt regularly notifies the application about its battery level. To listen to belt battery notifications, you must implement the `BeltControllerDelegate` interface. The method `on_belt_battery_notified()` is called when an battery notification is received.

See [examples/belt_battery_level.py](https://github.com/feelSpace/pybelt/blob/main/examples/belt_battery_level.py).
