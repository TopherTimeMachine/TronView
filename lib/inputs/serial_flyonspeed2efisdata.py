#!/usr/bin/env python

# Serial input source
# Fly on speed gen 2 box serial csv format
# 2/2/2019 Christopher Jones

from ._input import Input
from lib import hud_utils
import serial
import struct
from lib import hud_text
import time

class serial_flyonspeed2efisdata(Input):
    def __init__(self):
        self.name = "serial_flyonspeed2efisdata"
        self.version = 1.0
        self.inputtype = "serial"

    def initInput(self,num,aircraft):
        Input.initInput( self,num, aircraft )  # call parent init Input.
        
        if(self.PlayFile!=None and self.PlayFile!=False):
            if self.PlayFile==True:
                defaultTo = "flyonspeed2efisdata_data1.csv"
                self.PlayFile = hud_utils.readConfig(self.name, "playback_file", defaultTo)
            self.ser,self.input_logFileName = Input.openLogFile(self,self.PlayFile,"r")
            self.isPlaybackMode = True
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

    # close this data input 
    def closeInput(self,aircraft):
        if self.isPlaybackMode:
            self.ser.close()
        else:
            self.ser.close()

    #############################################
    ## Function: readMessage
    def readMessage(self, aircraft):
        if aircraft.errorFoundNeedToExit:
            return aircraft;
        try:
            x = 0
            msg = ""
            while x != 10:  # wait for CR (10) because this is the end of line of csv file.
                t = self.ser.read(1)
                if len(t) != 0:
                    x = ord(t)
                    msg += t
                    #print(t)
                else:
                    if self.isPlaybackMode:  # if no bytes read and in playback mode.  then reset the file pointer to the start of the file.
                        self.ser.seek(0)
                    return aircraft
            msgArray = msg.split(",")  # split up csv format
            if len(msgArray) == 23:  # should be 23 different values. if not then we didn't get a good line.

                aircraft.msg_last = msg
                # format for csv file from gen 2 box is:
                # 0         1    2            3   4           5       6    7   8             9        10 11 12 13      14        15       16           17            18              19       20      21      22              
                # timeStamp,Pfwd,PfwdSmoothed,P45,P45Smoothed,PStatic,Palt,IAS,AngleofAttack,flapsPos,Ax,Ay,Az,efisIAS,efisPitch,efisRoll,efisLateralG,efisVerticalG,efisPercentLift,efisPalt,efisVSI,efisAge,efisTime

                if True:
                    
                    aircraft.ias = float(msgArray[13])  
                    aircraft.pitch = float(msgArray[14])  
                    aircraft.roll = float(msgArray[15])  

                    aircraft.aoa = float(msgArray[18]) # aoa percent of lift.

                    aircraft.BALT = int(msgArray[19]) 

                    aircraft.vsi = int(msgArray[20]) 
                    aircraft.msg_count += 1

                    if self.isPlaybackMode:  #if playback mode then add a delay.  Else reading a file is way to fast.
                        time.sleep(.05)
                    else:
                        self.ser.flushInput()  # flush the serial after every message else we see delays
                    return aircraft
                else:
                    aircraft.msg_unknown += 1 # unknown message found.

            else:
                aircraft.msg_bad += 1 # count this as a bad message
                if self.isPlaybackMode:  #if playback mode then add a delay.  Else reading a file is way to fast.
                    time.sleep(.01)
                else:
                    self.ser.flushInput()  # flush the serial after every message else we see delays
                return aircraft
        except ValueError as ex:
            print("flyonspeed2efisdata data conversion error")
            aircraft.errorFoundNeedToExit = True
        except serial.serialutil.SerialException:
            print("flyonspeed2efisdata serial exception")
            aircraft.errorFoundNeedToExit = True
        return aircraft



    #############################################
    ## Function: printTextModeData
    def printTextModeData(self, aircraft):
        hud_text.print_header("Decoded data from Input Module: %s"%(self.name))
        hud_text.print_object(aircraft)
        hud_text.print_DoneWithPage()

# vi: modeline tabstop=8 expandtab shiftwidth=4 softtabstop=4 syntax=python
