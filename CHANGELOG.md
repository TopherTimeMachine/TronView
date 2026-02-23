# Changelog

## [0.0.35] - 2026-02-22

- fixes for g3x and serial port detect



## [0.0.34] - 2025-06-20

- text formating. and help updates.
- meshtastic gps updates
- fixed install icon on desktop for debian



## [0.0.33] - 2025-04-21

- meshtastic target scope
- meshtastic send messages and location
- FAA database n number search
- target scope update, mouse wheel support
- track flight number vs n number from stratux



## [0.0.32] - 2025-04-07

- meshtastic fixes for merging node data into dataship targets.
- added script for faa database download and sqlite creation



## [0.0.31] - 2025-04-07

- video in screen module



## [0.0.30] - 2025-03-22

- Gauges show color ranges. different modes. alpha transparency.
- text parsing better.
- support knots,mph,kph,c,f.. using format_specifier example {airData[0].IAS:kts}
- added image object. supports alpha. saves base64 in screen json. scale or fit modes.



## [0.0.29] - 2025-03-13

- sub menu work
- variable selection
- theme updates for gui
- fixes for gauges (bar and arc).  now pick from drop down.
- updated engine template.



## [0.0.28] - 2025-03-10

- data logging work. _input.py saves to correct file.




## [0.0.27] - 2025-02-26

- serial unique names using udev script for pi. /etc/udev/rules.d/99-tronview-serial.rules
- save last console logs file.
- added view option in menu to see last log



## [0.0.26] - 2025-02-23

- serial port list menu.
- templates clean up
- dropdown menu refactor
- config file updates


## [0.0.25] - 2025-02-19

- refactor work.
- template updates.
- fix to save and load text and segment text in json.
- menu updates.

## [0.0.24] - 2025-02-01

- nmea gps test script added



## [0.0.23] - 2025-01-05

- 3d tests added
- update for default screen json
- dynon skyview input updates. nav and engine
- fix for yaw in imu of stratux
- fix for bouy if mag_head is None


## [0.0.22] - 2024-12-08

- New 16 segment style text module for retro text.
- Heading module fix
- fix for to front and back buttons.
- updated md
- work on event manager



## [0.0.21] - 2024-12-06

- menu system updates
- new live input picker menu
- update from git. and reload run.sh
- main.py fixes for 100 inputs
- added i2c test script
- bno055 and bno085 init fixes. auto set address for 2nd imu.


## [0.0.20] - 2024-12-06
### Added
- Added Changelog!
- Support for versioning
- Growl notifications

### Changed
- Refactored lots
