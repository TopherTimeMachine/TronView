#!/usr/bin/env python

# Serial input source
# GRT EIS engine data
# 11/22/2024  Created GRT EIS input. Topher
# 2/9/2025   Dataship refactor. Topher

from ._input import Input
from lib import hud_utils
from . import _utils
import serial
import struct
from lib import hud_text
import binascii
import time
import traceback
from lib.common.dataship.dataship_imu import IMUData
from lib.common.dataship.dataship import Dataship
from lib.common.dataship.dataship_nav import NavData
from lib.common.dataship.dataship_engine_fuel import EngineData, FuelData
from lib.common.dataship.dataship_gps import GPSData
from lib.common.dataship.dataship_air import AirData
import struct  # Add this import at the top with other imports


class serial_grt_eis(Input):
    def __init__(self):
        self.name = "serial_grt_eis"
        self.version = 1.0
        self.inputtype = "serial"
        self.engineData = EngineData()

    def initInput(self,num,dataship: Dataship):
        Input.initInput(self,num,dataship)  # call parent init Input.
        self.output_logBinary = True
        print("initInput %d: %s playfile: %s"%(num,self.name,self.PlayFile))
        if(self.PlayFile!=None and self.PlayFile!=False):
            # Get playback file.
            if self.PlayFile==True:
                defaultTo = "GRT_EIS_1.bin"
                self.PlayFile = hud_utils.readConfig(self.name, "playback_file", defaultTo)
            self.ser,self.input_logFileName = Input.openLogFile(self,self.PlayFile,"rb")
            self.isPlaybackMode = True
        else:
            self.efis_data_port = hud_utils.readConfig(self.name, "port", "/dev/ttyS0")
            self.efis_data_baudrate = hud_utils.readConfigInt(self.name, "baudrate", 9600)

            # open serial connection
            self.ser = serial.Serial(
                port=self.efis_data_port,
                baudrate=self.efis_data_baudrate,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS,
                timeout=1,
            )

        # create a empty engine data object.
        self.engineData = EngineData()
        self.engineData.id = "grt_eis_engine"+str(len(dataship.engineData))
        self.engineData.name = self.name
        self.engine_index = len(dataship.engineData)  # Start at 0
        print("new grt_eis engine "+str(self.engine_index)+": "+str(self.engineData))
        dataship.engineData.append(self.engineData)

    def closeInput(self,aircraft):
        if self.isPlaybackMode:
            self.ser.close()
        else:
            self.ser.close()

    def readMessage(self, dataship: Dataship):
        if self.shouldExit == True: dataship.errorFoundNeedToExit = True
        if dataship.errorFoundNeedToExit: return dataship
        if self.skipReadInput == True: return dataship
        
        try:
            # Look for header sequence FE FF FE
            while True:
                b1 = self.ser.read(1)
                if not b1:  # Handle timeout/no data
                    if self.isPlaybackMode:
                        self.ser.seek(0)
                        print("GRT EIS file reset")
                    return dataship
                
                if b1[0] != 0xFE:
                    continue
                    
                b2 = self.ser.read(1)
                if not b2 or b2[0] != 0xFF:
                    continue
                    
                b3 = self.ser.read(1)
                if not b3 or b3[0] != 0xFE:
                    continue
                    
                break  # Found header sequence

            # Read the rest of the frame (63 bytes)
            frame = self.ser.read(63)
            if len(frame) != 63:
                return dataship

            # Validate checksum
            checksum = 0
            for b in frame[:-1]:
                checksum += b
            checksum = (~checksum) & 0xFF
            
            if checksum != frame[-1]:
                dataship.msg_bad += 1
                return dataship

            ## example line data:
            ## 

            # Parse the frame using struct
            (tach, cht1, cht2, cht3, cht4, cht5, cht6,
             egt1, egt2, egt3, egt4, egt5, egt6,
             aux5, aux6, aspd, alt, volt, fuel_flow,
             unit, carb, roc_sign, oat,
             oil_temp, oil_press, aux1, aux2, aux3, aux4,
             coolant, eti, fuel_qty, hrs, mins, secs,
             end_hrs, end_mins, baro, mag_head, spare) = struct.unpack(
                '>H6H6H2HhHHBbbhHB4HHHHBBBHHB', frame[:-1])
            
            # Update aircraft engine data
            self.engineData.RPM = tach
            self.engineData.OilTemp = oil_temp
            self.engineData.OilPress = oil_press
            self.engineData.FuelFlow = round(fuel_flow * 0.1, 1)  # Adjust units as needed
            
            # Update CHTs
            for i, cht in enumerate([cht1, cht2, cht3, cht4, cht5, cht6]):
                self.engineData.CHT[i] = cht
                
            # Update EGTs
            for i, egt in enumerate([egt1, egt2, egt3, egt4, egt5, egt6]):
                self.engineData.EGT[i] = egt

            self.engineData.CoolantTemp = coolant
            #self.engineData.oat = oat
            
            # Update message counts
            self.engineData.msg_count += 1

            if self.isPlaybackMode:
                time.sleep(0.01)  # Add delay in playback mode

            if self.output_logFile is not None:
                header = bytearray([0xFE, 0xFF, 0xFE])
                Input.addToLog(self, self.output_logFile, header)
                Input.addToLog(self, self.output_logFile, frame)

            return dataship

        except serial.serialutil.SerialException as e:
            print(e)
            print("grt_eis serial exception")
            traceback.print_exc()
            dataship.errorFoundNeedToExit = True
            
        return dataship

# vi: modeline tabstop=8 expandtab shiftwidth=4 softtabstop=4 syntax=python
