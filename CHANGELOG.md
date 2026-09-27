# Changelog

## [0.0.36] - 2026-09-27

HUD performance work (Epic Optix 60+ FPS lessons) and fixes for units / heading / altitude reference mix ups.

### Performance
- New `Module.getDrawSurface(pos)`: modules draw straight onto the display through a cached subsurface at the module position (module local coordinates, clipped to the module) instead of clearing a full size surface and blitting it every frame. Falls back to an offscreen surface if the module is partly off the top/left of the screen.
- Direct drawing used by horizon_v2, cdi, gcross, trafficscope and traffic_bar. Output is pixel identical to before.
- horizon_v2:
  - roll sin/cos computed once per frame instead of once per ladder line; +/-10 degree winglet rotation uses constants.
  - pitch ladder numbers are rendered once and cached.
  - dashed (negative pitch) lines drawn with plain float math, no temporary Point objects.
  - ladder lines completely above/below the module are skipped.
  - no longer builds a new class object every frame for the adjusted attitude.
  - measured horizon draw time ~3.0 ms -> ~0.4 ms (headless, 1280x720).
- rollindicator: rotates only the small pointer (not a 360x360 surface) and caches rotations per 0.5 degree.
- heading: tape surface reused instead of reallocating two surfaces every frame; track marker drawn on the same surface (one blit).
- trafficscope: static rings/scale stay cached; base and targets drawn directly to the display.
- graphic mode: dropdown overlay surface created once instead of every frame.
- Whole app, uncapped frame rate, headless 1280x720 stratux playback: default screen 158 -> 224 FPS, EFIS_XL 76 -> 95 FPS.

### Added
- Frame profiler in view mode. Press `d`:
  - debug 1: `FPS | draw | present | idle` shown bottom left (module draw time, `pygame.display.update()` time, frame limiter wait).
  - debug 2: also shows per module draw time (previously only available in edit mode).
- `GPSData.get_mag_decl()`: magnetic declination (East positive). Uses the input's Mag_Decl if provided, else computed from Lat/Lon with the World Magnetic Model and cached (recalculated only after ~0.5 degree of movement).
- `hud_utils.readConfigFloat()`.
- docs/dev/profiling.MD: built in profiler usage and performance / units guidelines for module authors.
- config_example.cfg: `window=1280,720` note for Epic Optix HUD (~56% fewer pixels than 1920x1080) and `maxframerate=60`.

### Changed
- Flight path marker (horizon_v2):
  - vertical position is the flight path angle computed from vertical speed and ground speed (falls back to TAS/IAS), referenced to aircraft pitch using the pitch ladder pixels/degree. Previously VSI/2 pixels.
  - horizontal drift = GPS true track - true heading (magnetic heading + declination), using the FOV pixels/degree (conformal). Clamped to stay on screen. Track/FPA ignored below 20 mph.
  - smoothing changed to an exponential moving average.
  - turn rate lead term removed (units differ between inputs and it crashed when turn rate was None).
- HUD traffic targets (horizon_v2) use true heading, the same pixels/degree, pitch and roll as the pitch ladder so they stay registered to it. Label shows distance and altitude difference instead of a debug angle.
- trafficscope only draws targets inside the scope range (outer ring).
- `fov_x` option in horizon_v2 / traffic_bar is a float.
- Stratux speeds converted to mph to match the rest of the dataship (ground speed, traffic target speed, AHRS IAS).

### Fixed
- HUD traffic targets were never drawn (inverted heading check in horizon_v2 draw_target).
- Ghost FPM drift was always zero (heading was compared with itself).
- Magnetic heading was compared directly with true GPS track / ADS-B bearing in the FPM, HUD targets, trafficscope, traffic_bar and the heading tape track marker. Declination now applied.
- `ignore_traffic_beyond_distance` was hard coded to 30 and never read from config. Now read from `[Main]` again (default 30, 0 = no limit, statute miles). The old misspelled `ignore_traffic_beyound_distance` is still accepted with a warning.
- Target cleanUp skipped targets when removing old ones (list modified while iterating).
- Stratux:
  - ownship report altitude is pressure altitude but was stored as GPS altitude. Now stored in `AltPressure` and used as the traffic altDiff reference (same datum as traffic altitudes).
  - geometric altitude message (11) was stored as pressure altitude and labeled meters. Now sets GPS `Alt` in feet.
  - 0xFFF (invalid) ownship altitude handled.
  - AHRS VSI and pressure altitude were written to non existent fields (`vsi`, `PALT`); now `VSI` and `Alt_pres`.
- Buoy altitude uses the same altitude datum as altDiff.
- `nm` text format specifier multiplied statute miles by 1.852 (km factor); now 0.868976.
- `fov_x` config was truncated to an int (13.942 -> 13), and a decimal value in config.cfg would crash.
- horizon_v2 center marker was offset twice when the module was not at 0,0; center mode 5 drew part of it straight to the screen.
- traffic_bar x position was offset twice and bearings didn't wrap at 0/360.
- rollindicator pointer was drawn away from the scale when positioned by the screen; roll point size option rescaled the wrong surface; crash when roll is None.
- gcross "NO VSI DATA" message was never shown; `TargetWingSpan` typo.
- Dashed pitch lines divided by zero on a zero length line.
- View mode crashed on mouse wheel before any click, and on touch (FINGERDOWN) events; touch coordinates are now scaled to the screen.

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
