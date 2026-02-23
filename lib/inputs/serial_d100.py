#!/usr/bin/env python

# Serial input source
# Dynon D10 and D100
# 2/2/2019  Topher
# 11/6/2024  Added IMU data.

from ._input import Input
from lib import hud_utils
import serial
import struct
from lib import hud_text
import time
import traceback
from lib.common.dataship.dataship import IMUData
from lib.common.dataship.dataship import Dataship
from lib.common.dataship.dataship_air import AirData

class serial_d100(Input):
    def __init__(self):
        self.name = "serial_d100"
        self.version = 1.0
        self.inputtype = "serial"
        self.imuData = IMUData()
        self.airData = AirData()

    def initInput(self,num,dataship: Dataship):
        Input.initInput( self,num, dataship )  # call parent init Input.
        self.msg_unknown = 0
        self.msg_bad = 0
        
        if(self.PlayFile!=None and self.PlayFile!=False):
            # load log file to playback.
            if self.PlayFile==True:
                defaultTo = "dynon_d100_data1.txt"
                self.PlayFile = hud_utils.readConfig(self.name, "playback_file", defaultTo)
            self.ser,self.input_logFileName = Input.openLogFile(self,self.PlayFile,"r")
        else:
            self.efis_data_port = hud_utils.readConfig(self.name, "port", "/dev/ttyS0")
            self.efis_data_baudrate = hud_utils.readConfigInt( self.name, "baudrate", 115200 )

            # open serial connection.
            self.ser = serial.Serial(
                port=self.efis_data_port,
                baudrate=self.efis_data_baudrate,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS,
                timeout=1,
            )

        # create a empty imu object.
        self.imuData = IMUData()
        self.imuData.id = "d100_imu"+str(len(dataship.imuData))
        self.imuData.name = self.name
        self.imu_index = len(dataship.imuData)  # Start at 0
        dataship.imuData.append(self.imuData)
        self.last_read_time = time.time()
        self.imuData.turn_rate = 0  # initialize to 0

        # create a empty air object.
        self.airData = AirData()
        self.airData.id = "d100_air"+str(len(dataship.airData))
        self.airData.name = self.name
        self.air_index = len(dataship.airData)  # Start at 0
        dataship.airData.append(self.airData)
        self.airData.VSI = 0  # initialize to 0


    # close this data input 
    def closeInput(self,aircraft):
        if self.isPlaybackMode:
            self.ser.close()
        else:
            self.ser.close()

    #############################################
    ## Function: readMessage
    def readMessage(self, dataship: Dataship):
        if dataship.errorFoundNeedToExit:
            return dataship;
        try:
            x = 0
            while x != 10:  # wait for CR (10) because this is the end of line for a message. (there is no start of a line char on the d10/100 series )
                t = self.ser.read(1)
                if len(t) != 0:
                    x = ord(t)
                else:
                    if self.isPlaybackMode:  # if no bytes read and in playback mode.  then reset the file pointer to the start of the file.
                        self.ser.seek(0)
                    return dataship
            msg = self.ser.read(51)  
            if len(msg) == 51:
                msg = (msg[:51]) if len(msg) > 51 else msg
                self.imuData.msg_last = msg
                # 8b        4b    5b   3b  4b   5b   4b        3b        3b         2b   6b                2b          2s  
                HH,MM,SS,FF,pitch,roll,yaw,IAS, Alt, TurnRate, LatAccel, VertAccel, AOA, StatusBitMaskHex, InteralUse, Checksum = struct.unpack(
                    "2s2s2s2s4s5s3s4s5s4s3s3s2s6s2s2s", str.encode(msg)
                )

                self.airData.sys_time_string = "%d:%d:%d"%(int(HH),int(MM),int(SS))
                self.time_stamp_string = self.airData.sys_time_string

                self.imuData.roll = int(roll) / 10
                self.imuData.pitch = int(pitch) / 10
                self.airData.IAS = round(int(IAS) * 0.224,1)  # airspeed in units of 1/10 m/s (1555 = 155.5 m/s) convert to MPH

                self.airData.AOA = int(AOA)
                self.imuData.yaw = int(yaw)
                self.imuData.mag_head = self.imuData.yaw
                #aircraft.baro = (int(Baro) + 2750.0) / 100   # no baro for D100 data.
                #aircraft.baro_diff = aircraft.baro - 29.921
                #aircraft.alt = int( int(Alt) + (aircraft.baro_diff / 0.00108) )  # 0.00108 of inches of mercury change per foot.
                self.imuData.slip_skid = float(LatAccel) / 100  # slip skid 00 to 99, lateral g's in units of 1/100 g (99 = 0.99 g's).
                self.imuData.vert_G = float(VertAccel) / 100  #
                # check status if bit 1 is 0.. then.
                statusInt = int(StatusBitMaskHex, 16)  # convert hex-ascii to int value
                if statusInt & 1 == 0:
                    self.airData.Alt_baro = int(Alt) * 3.28084 # convert meters to feet.
                    self.imuData.turn_rate = int(TurnRate)  # set turn rate.
                else:
                    self.airData.Alt_baro = int(Alt) * 3.28084 # convert meters to feet.
                    self.airData.VSI = int(TurnRate)  # vert speed for D100 data

                self.airData.Alt = self.airData.Alt_baro # set alt to alt_baro

                # Update IMU data hz info if in debug mode.
                if dataship.debug_mode > 0:
                    current_time = time.time() # calculate hz.
                    self.imuData.hz = round(1 / (current_time - self.last_read_time), 1)
                    self.last_read_time = current_time

                self.imuData.msg_count += 1

                if self.isPlaybackMode:  #if playback mode then add a delay.  Else reading a file is way to fast.
                    time.sleep(.05)
                #else:
                #    self.ser.flushInput()  # flush the serial after every message else we see delays

                # add to log file
                if self.output_logFile != None:
                    Input.addToLog(self,self.output_logFile,msg+'\n')
                return dataship

            else:
                self.msg_bad += 1 # count this as a bad message
                if self.isPlaybackMode:  #if playback mode then add a delay.  Else reading a file is way to fast.
                    time.sleep(.01)
                #else:
                #   self.ser.flushInput()  # flush the serial after every message else we see delays
                return dataship
        except ValueError as ex:
            print("dynon d100 data conversion error")
            print(ex)
            traceback.print_exc()
            dataship.errorFoundNeedToExit = True
        except serial.serialutil.SerialException:
            print("dynon d100 serial exception")
            dataship.errorFoundNeedToExit = True
            traceback.print_exc()
        except Exception as e:
            dataship.errorFoundNeedToExit = True
            print(e)
            print(traceback.format_exc())
        return dataship



# vi: modeline tabstop=8 expandtab shiftwidth=4 softtabstop=4 syntax=python
