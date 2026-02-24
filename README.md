<p align="center">
  <img src="docs/imgs/logo_black.png?raw=true" alt="logo">
</p>

# TronView
Project for connecting EFIS or any external sensor data to a Screen, HUD, or AR glasses.  This was created for the aviation community but can be used for any application where you want to display data in a custom GUI (and interact with it).

![cockpit1](docs/efis_cockpit1.jpeg?raw=true)
## Active development! (Feb 2026)
If you want to help with development or testing please join our [Join Discord](https://discord.gg/pdnxWa32aW) sever.
We are working on several new features.
- AI Hat + 2 intergation
- MeshCore intergration.
- Meshtastic integration (Done)
- Video Input (Done)
- Show/Hide screen modules based on key commands or other inputs. (event handlers)
- Moving Map.

## Features Include:
- Build custom efis or hud screens or AR glasses screen. (or any kinda of screen you want)
- Can build any kind of UI for external sensors or external data.
- Record and Playback flight log data ( and fast forward through playback )
- All screens look and work the same for all supported data input.
- All display screen sizes and ratios supported.
- Built in editor to make creating or editing your own screen.
- Text mode
- Touch screen support
- 30 + FPS on Raspberry Pi 4/5 (60+ FPS on Mac M1)
- Remote keypad / user input support.
- Display flight data in Knots, Standard, Metric, F or C
- Designed for Raspberry Pi 4/5 but also runs on Mac OSx, Windows, and other linux systems.
- Show NAV needles for approaches. (If NAV data is available)
- Use multiple data input sources, (MGL, G3x, Dynon, GRT EIS, iLevil BOM, Stratux, Analog CDI via ADS1115, IMU BNO055 & BNO085, Generic Serial Logger, Joystick)


# Quick Start for Raspberry Pi and Mac OS

[Quick Start for Raspberry Pi](docs/quick_start_pi.MD)

[Quick Start for Mac OS](docs/quick_start_macos.MD)

## Running TronView on mobile uConsole device.

Run TronView as a ADSB traffic and meshtastic node monitor.  Show all targets on the same map.

![uConsole](docs/screenshots/uconsole1.jpg?raw=true)

## 3d wire frame terrain view through AR glasses (work in progress)

![3d_mesh](docs/screenshots/tv_mesh.png?raw=true)

## 3d synthetic world (work in progress)

![3d_world](docs/screenshots/tv3d.png?raw=true)

## Use as backup display screen on dash

![cockpit2](docs/efis_cockpit2.jpeg?raw=true)

## Editor Screenshot
![screenshot1](docs/screenshots/screenshot_2_editor.png?raw=true)

## F18 Style HUD
![rv8Hud](docs/efis_HUD_rv8.jpg?raw=true)

## Text Mode
![hud_animation](docs/efis_screenshot_text.png?raw=true)

## Engine/System Display in Classic Pinzgauer Swiss Military Vehicle
![pinzgauer](docs/imgs/pinz1.jpeg?raw=true)


# About

This is a python3 application that will take in data from different input sources, process them into a common format, then output (draw) 
them to custom screens.  The system is created to have the inputs and screens seperate and non-dependent of each other.  
For example a user running a MGL iEFIS can run the same screen as a user with a Dynon D100.  Issues can come up with a input source does not 
have all the data available as other input sources do.  But if the screen is written well enough it will hide or show data if it's available.


## Currently supported input sources:

MGL iEFIS

Garmin G3x

Dynon Skyview

Dynon D10/100

GRT EIS

Levil BOM (wifi)

Stratux or any stratux compatiable device (wifi)

IFR Navigator (Analog CDI) (ADS 1115)

BNO055 IMU (9DOF) and BNO085 (9DOF)

Generic serial logger (Used for recording any serial data)

Joystick (USB or Bluetooth)

Meshtastic SDK

We are using the rapberry pi 4, or 5 for taking serial data from a EFIS (MGL,Dynon,G3x,etc) and displaying a graphical Display out the hdmi output on the pi.  This can be displayed on a screen (touchscreen, etc) ,a HUD, or glasses.  

Code is written in Python 3.7 and the Pygame-CE 2.0 module for handling the graphics.


# More details

Analog CDI from IFR Navigator: [input analog details](docs/input_analog.MD)

Config example:  [config_example.cfg](config_example.cfg)

Lots of different efis test data: [Test Data](docs/efis_data.MD)

IncludesF-18 style HUD screen: [screen_F18.MD](docs/screen_F18.MD)

# Join our Discord server

We are active on Discord helping each other with development and testing.  Come help or share ideas.

[Join Discord](https://discord.gg/pdnxWa32aW)

