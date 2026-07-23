#!/usr/bin/env python

# Serial input source
# OnSpeed Gen3 display-serial wire (`#4` framing, 86-byte frames at 40 Hz)
#
# Reads the native display-serial stream an OnSpeed Gen3 box emits from its
# display UART (115200 8N1, one-way; the box default SERIALOUTFORMAT=ONSPEED).
# This is the same wire the OnSpeed M5Stack secondary display consumes, so
# TronView receives the box's full data set: attitude, IAS, percent-lift AOA,
# the per-flap calibrated indexer band anchors, flap position/travel, VSI,
# OAT, G loads, G-onset rate, deceleration rate, and the pilot's data-mark
# counter.
#
# Wire-format reference: https://dev.flyonspeed.org/reference/serial-protocol/
# Frame parser: vendored in _onspeed_frame.py (kept in sync with the
# OnSpeed-Gen3 firmware repo, where it is byte-parity-tested against the
# firmware's C++ encoder in CI).
#
# The wire is hard-versioned by its magic ("#4", OnSpeed firmware v4.25+).
# A frame from older firmware fails the magic check and is dropped — the
# display shows no data rather than mis-parsed data, by design.
#
# Values arrive PRE-SMOOTHED at 40 Hz — the box's own filter chain has
# already run — so this input applies NO smoothing of its own (no moving
# averages, no EMA).  Adding smoothing here would only add lag to a
# stall-proximity cue.
#
# Read pattern: each readMessage() call drains everything the OS has
# buffered, runs it all through the frame accumulator, and publishes the
# most recent complete valid frame.  Bounded work per call, no backlog
# growth, no flushInput() — the display always shows the newest frame even
# when the input thread is visited slower than 40 Hz.

from ._input import Input
from ._onspeed_frame import FRAME_LEN, FrameAccumulator
from lib import hud_utils
from lib import hud_text
import serial
import time
from lib.common.dataship.dataship import Dataship
from lib.common.dataship.dataship_imu import IMUData
from lib.common.dataship.dataship_air import AirData

KT_TO_MPH = 1.15078
FRAME_PERIOD_S = 0.025  # 40 Hz wire cadence (kDisplayFramePeriodMs in the firmware)


class serial_onspeedaoa(Input):
    def __init__(self):
        self.name = "serial_onspeedaoa"
        self.version = 2.0
        self.inputtype = "serial"
        self.accumulator = FrameAccumulator()
        self.imuData = IMUData()
        self.airData = AirData()

    def initInput(self, num, dataship: Dataship):
        Input.initInput(self, num, dataship)  # call parent init Input.

        if(self.PlayFile != None and self.PlayFile != False):
            # load playback file (raw #4 wire bytes).
            if self.PlayFile == True:
                defaultTo = "onspeed_aoa_1.dat"
                self.PlayFile = hud_utils.readConfig(self.name, "playback_file", defaultTo)
            self.ser, self.input_logFileName = Input.openLogFile(self, self.PlayFile, "rb")
            self.isPlaybackMode = True
        else:
            self.efis_data_port = hud_utils.readConfig(self.name, "port", "/dev/ttyS0")
            self.efis_data_baudrate = hud_utils.readConfigInt(self.name, "baudrate", 115200)

            # open serial connection.
            self.ser = serial.Serial(
                port=self.efis_data_port,
                baudrate=self.efis_data_baudrate,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS,
                timeout=1,
            )

        # log raw wire bytes when recording.
        self.output_logBinary = True

        # create an imu object for attitude/rates/G from the box.
        self.imuData = IMUData()
        self.imuData.name = "onspeed_imu"
        self.imuData.id = "onspeed_imu" + str(len(dataship.imuData))
        dataship.imuData.append(self.imuData)

        # create an air object for IAS/alt/AOA/VSI/OAT + OnSpeed extras.
        self.airData = AirData()
        self.airData.name = "onspeed_air"
        self.airData.id = "onspeed_air" + str(len(dataship.airData))
        dataship.airData.append(self.airData)

        self.last_read_time = time.time()
        # playback pacing state: frames are released against the wall
        # clock at the wire's 40 Hz so a recording plays in real time
        # regardless of how often the input thread visits.
        self.playback_t0 = time.monotonic()
        self.playback_frames = 0

    # close this data input
    def closeInput(self, aircraft):
        self.ser.close()

    #############################################
    ## Function: readMessage
    # Drain whatever bytes are available, parse every complete frame,
    # publish the most recent one.
    def readMessage(self, dataship: Dataship):
        if dataship.errorFoundNeedToExit:
            return dataship
        try:
            if self.isPlaybackMode:
                # release frames against the wall clock at the wire's
                # 40 Hz, so the recording plays in real time no matter how
                # often the input thread visits.
                now = time.monotonic()
                frames_due = int((now - self.playback_t0) / FRAME_PERIOD_S) - self.playback_frames
                if frames_due <= 0:
                    return dataship
                if frames_due > 40:
                    # long stall (suspend, blocked thread): rebase instead of
                    # sprinting through the backlog.
                    self.playback_t0 = now - 40 * FRAME_PERIOD_S
                    self.playback_frames = 0
                    frames_due = 40
                data = self.ser.read(FRAME_LEN * frames_due)
                self.playback_frames += frames_due
                if len(data) == 0:
                    self.ser.seek(0)  # loop the file.
                    self.playback_t0 = now
                    self.playback_frames = 0
                    return dataship
            else:
                waiting = self.ser.in_waiting
                # block (up to the port timeout) for the first byte, then
                # take everything else the OS has buffered.
                data = self.ser.read(waiting if waiting > 0 else 1)
                if len(data) == 0:
                    return dataship

            frames = self.accumulator.feed(data)

            if self.output_logFile != None:
                Input.addToLog(self, self.output_logFile, data)

            if not frames:
                return dataship

            # keep-latest: older frames in this chunk are superseded.
            self.publish_frame(frames[-1])
            self.airData.msg_count += len(frames)
            self.imuData.msg_count += len(frames)

            if dataship.debug_mode > 0:
                current_time = time.time()
                self.imuData.hz = round(len(frames) / max(current_time - self.last_read_time, 1e-6), 1)
                self.last_read_time = current_time

        except serial.serialutil.SerialException:
            print("serial_onspeedaoa serial exception")
            dataship.errorFoundNeedToExit = True
        return dataship

    #############################################
    ## Function: publish_frame
    # Write one parsed frame into the dataship objects.
    def publish_frame(self, f):
        self.imuData.pitch = f.pitch_deg
        self.imuData.roll = f.roll_deg
        self.imuData.turn_rate = f.turnrate_dps
        self.imuData.vert_G = f.vertical_g
        # The wire's lateralG is body-frame (positive = airframe
        # accelerating rightward); the slip ball deflects opposite.  Negate
        # here so slip_skid matches what the serial_g3x input produces for
        # the same flight state (the Garmin wire carries the negated value)
        # and the slipskid module renders identically from either source.
        self.imuData.slip_skid = -f.lateral_g

        air = self.airData
        if f.ias_valid:
            air.IAS = f.ias_kts * KT_TO_MPH
            # percent-lift AOA, 0..100 — same semantic as the AOA percent
            # the serial_g3x input reads from a Garmin wire, at tenths
            # resolution.  0 below the box's audio-mute airspeed.
            air.AOA = f.percent_lift_pct
        else:
            # air-data-invalid wire sentinel (on the ground, pitot inside
            # the noise floor).  None renders as no-data.
            air.IAS = None
            air.AOA = None
        # The wire carries pressure altitude; the box has no baro setting.
        air.Alt_pres = f.palt_ft
        air.Alt = f.palt_ft
        air.BALT = f.palt_ft
        air.VSI = f.vsi_fpm
        air.OAT = (f.oat_c * 1.8) + 32  # c to f

        # OnSpeed extras: the per-flap calibrated indexer band anchors
        # (percent-lift units, snapped to the active flap detent — they
        # re-anchor at every detent change, in lockstep with the box's
        # audio cues), the visual L/Dmax pip, flap position/travel, and
        # rate cues.  The hud/aoa module uses the anchors to draw the
        # indexer bands from the aircraft's own calibration; everything
        # here is also bindable from the screen editor.
        air.OnSpeed_tonesOnPctLift = f.tones_on_pct_lift
        air.OnSpeed_fastPctLift = f.onspeed_fast_pct_lift
        air.OnSpeed_slowPctLift = f.onspeed_slow_pct_lift
        air.OnSpeed_stallWarnPctLift = f.stall_warn_pct_lift
        air.OnSpeed_pipPctLift = f.pip_pct_lift
        air.OnSpeed_flapsDeg = f.flap_deg
        air.OnSpeed_flapsMinDeg = f.flaps_min_deg
        air.OnSpeed_flapsMaxDeg = f.flaps_max_deg
        air.OnSpeed_gOnsetRate = f.g_onset_rate
        air.OnSpeed_decelKtPerSec = f.decel_kt_per_sec
        air.OnSpeed_dataMark = f.data_mark

    #############################################
    ## Function: printTextModeData
    def printTextModeData(self, aircraft):
        hud_text.print_header("Decoded data from Input Module: %s" % (self.name))
        hud_text.print_object(aircraft)
        hud_text.print_DoneWithPage()


# Standalone smoke mode: open a port and print decoded frames.
#   python3 -m lib.inputs.serial_onspeedaoa /dev/ttyUSB0
if __name__ == "__main__":
    import sys

    port = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyS0"
    ser = serial.Serial(port=port, baudrate=115200, timeout=1)
    acc = FrameAccumulator()
    while True:
        chunk = ser.read(ser.in_waiting or 1)
        for f in acc.feed(chunk):
            print(
                f"ONSPEED: IAS {f.ias_kts:.1f}kt pctLift {f.percent_lift_pct:.1f}% "
                f"pitch {f.pitch_deg:.1f} roll {f.roll_deg:.1f} flaps {f.flap_deg} "
                f"bands {f.tones_on_pct_lift}/{f.onspeed_fast_pct_lift}/"
                f"{f.onspeed_slow_pct_lift}/{f.stall_warn_pct_lift} pip {f.pip_pct_lift}"
            )

# vi: modeline tabstop=8 expandtab shiftwidth=4 softtabstop=4 syntax=python
