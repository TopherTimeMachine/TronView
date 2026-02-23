#!/usr/bin/env python

# Serial input source
# MGL iEFIS
# 1/23/2019 Topher
# 11/4/2024 - optimize message parsing. round values. Added Yaw, fix for Mag_head.
# 11/6/2024  Added IMU data.
# 2/9/2025  Added gpsData object to the module. major refactor.

from ._input import Input
from lib import hud_utils
from . import _utils
import serial
import struct
from lib import hud_text
import binascii
import time
from lib.common.dataship.dataship import Dataship
from lib.common.dataship.dataship_imu import IMUData
from lib.common.dataship.dataship_gps import GPSData
from lib.common.dataship.dataship_engine_fuel import EngineData, FuelData
from lib.common.dataship.dataship_nav import NavData
from lib.common.dataship.dataship_air import AirData

import traceback

class serial_mgl(Input):
    def __init__(self):
        self.name = "serial_mgl"
        self.version = 1.0
        self.inputtype = "serial"

    def initInput(self,num,dataship:Dataship):
        self.msg_unknown = 0
        self.msg_bad = 0
        Input.initInput( self,num, dataship )  # call parent init Input.
        self.output_logBinary = True
        print("initInput %d: %s playfile: %s"%(num,self.name,self.PlayFile))
        if(self.PlayFile!=None and self.PlayFile!=False):
            # Get playback file.
            if self.PlayFile==True:
                defaultTo = "MGL_Flight1.bin"
                self.PlayFile = hud_utils.readConfig(self.name, "playback_file", defaultTo)
            self.ser,self.input_logFileName = Input.openLogFile(self,self.PlayFile,"rb")
            self.isPlaybackMode = True
        else:
            self.efis_data_port = hud_utils.readConfig(self.name, "port", "/dev/ttyS0")
            self.efis_data_baudrate = hud_utils.readConfigInt(
                self.name, "baudrate", 115200
            )

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
        self.imuData.id = "mgl_imu"
        self.imuData.name = self.name
        self.imuData.inputIndex = num
        self.imu_index = len(dataship.imuData)  # Start at 0
        print("new imu "+str(self.imu_index)+": "+str(self.imuData))
        # add imuData to dataship.imuData list.
        dataship.imuData.append(self.imuData)
        self.last_read_time = time.time()

        # create a empty gps object.
        self.gpsData = GPSData()
        self.gpsData.id = "mgl_gps"
        self.gpsData.name = self.name
        self.gps_index = len(dataship.gpsData)  # Start at 0
        print("new gps "+str(self.gps_index)+": "+str(self.gpsData))
        dataship.gpsData.append(self.gpsData)

        # create a empty engine object.
        self.engineData = EngineData()
        self.engineData.id = "mgl_engine"
        self.engineData.name = self.name
        self.engine_index = len(dataship.engineData)  # Start at 0
        print("new engine "+str(self.engine_index)+": "+str(self.engineData))
        dataship.engineData.append(self.engineData)

        # create a empty fuel object.
        self.fuelData = FuelData()
        self.fuelData.id = "mgl_fuel"
        self.fuelData.name = self.name
        self.fuel_index = len(dataship.fuelData)  # Start at 0
        print("new fuel "+str(self.fuel_index)+": "+str(self.fuelData))
        dataship.fuelData.append(self.fuelData)

        # create a empty nav object.
        self.navData = NavData()
        self.navData.id = "mgl_nav"
        self.navData.name = self.name
        self.nav_index = len(dataship.navData)  # Start at 0
        print("new nav "+str(self.nav_index)+": "+str(self.navData))
        dataship.navData.append(self.navData)

        # create a empty air object.
        self.airData = AirData()
        self.airData.id = "mgl_air"
        self.airData.name = self.name
        self.air_index = len(dataship.airData)  # Start at 0
        print("new air "+str(self.air_index)+": "+str(self.airData))
        dataship.airData.append(self.airData)

    def closeInput(self,dataship):
        if self.isPlaybackMode:
            self.ser.close()
        else:
            self.ser.close()

    #############################################
    ## Function: readMessage
    def readMessage(self, dataship:Dataship):
        if self.shouldExit == True: dataship.errorFoundNeedToExit = True
        if dataship.errorFoundNeedToExit: return dataship
        if self.skipReadInput == True: return dataship
        try:
            x = 0
            while x != 5:
                t = self.ser.read(1)
                if len(t) != 0:
                    x = ord(t)
                else:
                    if self.isPlaybackMode:  # if no bytes read and in playback mode.  then reset the file pointer to the start of the file.
                        self.ser.seek(0)
                        print("MGL file reset")
                    return dataship
            stx = ord(self.ser.read(1))

            if stx == 2:
                MessageHeader = self.ser.read(6)
                Message = 0
                if len(MessageHeader) == 6:
                    msgLength, msgLengthXOR, msgType, msgRate, msgCount, msgVerion = struct.unpack(
                        "!BBBBBB", MessageHeader
                    )

                    if msgType == 3:  # attitude information
                        Message = self.ser.read(32)
                        if len(Message) == 32:
                            # use struct to unpack binary data.  https://docs.python.org/2.7/library/struct.html
                            HeadingMag, PitchAngle, BankAngle, YawAngle, TurnRate, Slip, GForce, LRForce, FRForce, BankRate, PitchRate, YawRate, SensorFlags, Padding1, Padding2, Padding3, Checksum = struct.unpack(
                                "<HhhhhhhhhhhhBBBBi", Message
                            )
                            self.imuData.pitch = round(PitchAngle * 0.1, 1)  # truncate to 1 decimal place
                            self.imuData.roll = round(BankAngle * 0.1, 1)  #
                            self.imuData.yaw = round(YawAngle * 0.1, 1) 
                            if HeadingMag != 0:
                                self.imuData.mag_head = round(HeadingMag * 0.1,1)
                            else:
                                self.imuData.mag_head = 0
                            self.imuData.yaw = self.imuData.mag_head
                            self.imuData.turn_rate = round(TurnRate * 0.1, 1)
                            self.imuData.slip_skid = (Slip * 0.01 * -1) * 2 # convert to aircraft format -100 to 100.  postive is to left. #LRForce * 0.01 
                            self.imuData.vert_G = GForce * 0.01
                            self.imuData.msg_count += 1


                            if dataship.debug_mode > 0:
                                current_time = time.time()
                                # calculate hz.
                                self.imuData.hz = round(1 / (current_time - self.last_read_time), 1)
                                self.last_read_time = current_time
                            # # Update the IMU in the aircraft's imus dictionary
                            # dataship.imus[self.imu_index] = self.imuData
                            # # update the IMU position.
                            # self.imuData.updatePos(dataship.pitch, dataship.roll, dataship.yaw)


                    elif msgType == 2:  # GPS Message
                        Message = self.ser.read(48)
                        if len(Message) == 48:
                            Latitude, Longitude, GPSAltitude, AGL, NorthV, EastV, DownV, GS, TrackTrue, Variation, GPSStatus, SatsTracked, SatsVisible, HorizontalAccuracy, VerticalAccuracy, GPScapability, RAIMStatus, RAIMherror, RAIMverror, padding, Checksum = struct.unpack(
                                "<iiiiiiiHHhBBBBBBBBBBi", Message
                            )
                            if GS > 0:
                                self.gpsData.GndSpeed = round(GS * 0.06213712, 1) # convert to mph
                            self.airData.Alt_agl = AGL
                            self.gpsData.GndTrack = int((TrackTrue * 0.1) + 0.5)
                            self.gpsData.Mag_Decl = round(Variation * 0.1, 3) # Magnetic variation 10th/deg West = Neg
                            if (self.imuData.mag_head == None):  # if no mag heading use ground track
                                self.imuData.mag_head = self.gpsData.GndTrack
                            self.gpsData.Lat = Latitude / 180000
                            self.gpsData.Lon = Longitude / 180000
                            self.gpsData.Alt = GPSAltitude # ft MSL
                            self.gpsData.SatsVisible = SatsVisible
                            self.gpsData.SatsTracked = SatsTracked
                            self.gpsData.GPSStatus = GPSStatus
                            self.gpsData.msg_count += 1
                            ##if(self.textMode_showRaw==True): self.gpsData.msg_last = binascii.hexlify(Message) # save last message.
                            ##else: self.gpsData.msg_last = None

                    elif msgType == 1:  # Primary flight
                        Message = self.ser.read(36)
                        if len(Message) == 36:
                            PAltitude, BAltitude, ASI, TAS, AOA, VSI, Baro, LocalBaro, OAT, Humidity, SystemFlags, Hour, Min, Sec, Day, Month, Year,FTHour, FTMin,Checksum  = struct.unpack(
                                "<iiHHhhHHhBBBBBBBBBBi", Message
                            )
                            if ASI > 0:
                                self.airData.IAS = round(ASI * 0.06213712, 1) #idicated airspeed in 10th of Km/h.  * 0.05399565 to knots. * 0.6213712 to mph
                            if TAS > 0:
                                self.airData.TAS = round(TAS * 0.06213712, 1) # mph
                            # efis_alt = BAltitude
                            self.airData.Baro = (
                                round(LocalBaro * 0.0029529983071445, 4)
                            )  # convert from mbar to inches of mercury.
                            self.airData.AOA = AOA
                            self.airData.VSI = VSI
                            self.airData.Baro_diff = round(29.921 - self.airData.Baro, 4)
                            self.airData.Alt_pres = PAltitude
                            self.airData.Alt_baro = BAltitude
                            self.airData.Alt = int(
                                PAltitude - (self.airData.Baro_diff / 0.00108)
                            )  # 0.00108 of inches of mercury change per foot.
                            self.airData.OAT = int((OAT * 1.8) + 32) # convert from c to f
                            self.gpsData.GPSTime_string = "%d:%d:%d"%(Hour,Min,Sec)
                            #self.gpsData.GPSTime = "%d:%d:%d"%(Hour,Min,Sec)
                            self.time_stamp_min = Min
                            self.time_stamp_sec = Sec

                            self.airData.msg_count += 1

                            # Add safety checks before wind calculation
                            if self.airData.TAS is not None and self.gpsData.GndSpeed is not None \
                               and self.gpsData.GndTrack is not None and self.imuData.mag_head is not None \
                               and self.gpsData.Mag_Decl is not None:
                                self.airData.Wind_speed, self.airData.Wind_dir, self.airData.Wind_dir_corr = _utils.windSpdDir(
                                    self.airData.TAS * 0.8689758, # back to knots.
                                    self.gpsData.GndSpeed * 0.8689758, # convert back to knots
                                    self.gpsData.GndTrack,
                                    self.imuData.mag_head,
                                    self.gpsData.Mag_Decl,
                                )


                    elif msgType == 5:  # Traffic message
                        # MGL does not support traffic.  The docs say it is there, but it does not send it.
                        pass
                        # Message = self.ser.read(msgLength+6)
                        # if len(Message) == 4:
                        #     TrafficMode, NumOfTraffic, NumMsg, MsgNum = struct.unpack(
                        #         "!BBBB", Message
                        #     )
                        #     dataship.traffic.TrafficMode = TrafficMode
                        #     dataship.traffic.TrafficCount = NumOfTraffic
                        #     dataship.traffic.NumMsg = NumMsg
                        #     dataship.traffic.MsgNum = ThisMsgNum

                        # dataship.traffic.msg_count += 1
                        # if(self.textMode_showRaw==True): dataship.traffic.msg_last = binascii.hexlify(Message) # save last message.


                    # elif msgType == 30:  # Navigation message
                    #     Message = self.ser.read(56)
                    #     if len(Message) == 56:
                    #         # H     B            B         B        B       h=small int     H = Word        h       h     h       i=long  i       i     i     h=small h     h 
                    #         Flags, HSISource, VNAVSource, APMode, Padding, HSINeedleAngle, HSIRoseHeading, HSIDev, VDev, HeadBug, AltBug, WPDist, WPLat,WPLon,WPTrack,vor1r,vor2r,dme1,dme2,ILSDev,GSDev,GLSHoriz,GLSVert,Padding,Checksum = struct.unpack(
                    #             "<HBBBBhHhhhiiiihhhHHhhhhHi", Message
                    #         )
                    #         dataship.nav.NavStatus = hud_utils.get_bin(Flags)
                    #         dataship.nav.HSISource = HSISource
                    #         dataship.nav.VNAVSource = VNAVSource
                    #         dataship.nav.AP = APMode
                    #         dataship.nav.HSINeedle = HSINeedleAngle
                    #         dataship.nav.HSIRoseHeading = HSIRoseHeading
                    #         dataship.nav.HSIHorzDev = HSIDev
                    #         dataship.nav.HSIVertDev = VDev

                    #         dataship.nav.HeadBug = HeadBug
                    #         dataship.nav.AltBug = AltBug

                    #         dataship.nav.WPDist = round(WPDist * 0.0539957, 2) # KM (tenths) to NM (0.0539957), Statue Mile (.0621371) Conversion
                    #         dataship.nav.WPLat = WPLat / 180000
                    #         dataship.nav.WPLon = WPLon / 180000

                    #         dataship.nav.WPTrack = WPTrack

                    #         dataship.nav.ILSDev = ILSDev
                    #         dataship.nav.GSDev = GSDev
                    #         dataship.nav.GLSHoriz = GLSHoriz
                    #         dataship.nav.GLSVert = GLSVert

                    #         dataship.nav.msg_count += 1
                    #         if(self.textMode_showRaw==True): dataship.nav.msg_last = binascii.hexlify(Message) # save last message.
                    #         else: dataship.nav.msg_last = None

                    # elif msgType == 4:  # Various input states and signals
                    #     Message = self.ser.read(msgLength+6)
                    #     # todo... read message

                    # elif msgType == 11:  # fuel levels
                    #     Message = self.ser.read(4)
                    #     # H = Word (16 bit unsigned integer),  h=small (16 bit signed integer), B = byte, i = long (32 bit signed integer)
                    #     NumOfTanks  = struct.unpack( "<i", Message )
                    #     for x in range(NumOfTanks[0]):
                    #         TankMessage = self.ser.read(8)
                    #         Level,Type,TankOn,TankSensors  = struct.unpack("<iBBH", TankMessage)
                    #         dataship.fuel.FuelLevels[x] = round(Level * 0.02641729, 2) # convert liters to gallons

                    #     dataship.fuel.msg_count += 1
                    #     if(self.textMode_showRaw==True): dataship.fuel.msg_last = binascii.hexlify(Message) # save last message.
                    #     else: dataship.fuel.msg_last = None

                    # elif msgType == 10:  # Engine message
                    #     Message = self.ser.read(40)
                    #     if len(Message) == 40:
                    #         # H = Word,  h=small, B = byte, i = long
                    #         # B            B           B            B           H    H      H             H              H             h           h         h          h        h           h       h         H         H        H             H              h          H
                    #         EngineNumber, EngineType, NumberOfEGT, NumberOfCHT, RPM, Pulse, OilPressure1, OilPressure2, FuelPressure, CoolantTemp, OilTemp1, OilTemp2, AuxTemp1, AuxTemp2, AuxTemp3, AuxTemp4, FuelFlow, AuxFuel, ManiPressure, BoostPressure, InletTemp, AmbientTemp  = struct.unpack(
                    #             "<BBBBHHHHHhhhhhhhHHHHhH", Message
                    #         )

                    #         dataship.engine.NumberOfCylinders = NumberOfEGT
                    #         dataship.engine.RPM = RPM
                    #         dataship.engine.OilPress = round(OilPressure1 * 0.01450377,2) # In 10th of a millibar (Main oil pressure) convert to PSI
                    #         dataship.engine.OilPress2 = round(OilPressure2 * 0.01450377,2)
                    #         dataship.engine.FuelPress = round(FuelPressure * 0.01450377,2)
                    #         dataship.engine.CoolantTemp = round((CoolantTemp * 1.8) + 32,1) # C to F
                    #         dataship.engine.OilTemp = round((OilTemp1 * 1.8) + 32,1)  # convert from C to F
                    #         dataship.engine.OilTemp2 = round((OilTemp2 * 1.8) + 32,1) # convert from C to F
                    #         dataship.engine.FuelFlow = round(FuelFlow * 0.002642,2) # In 10th liters/hour convert to Gallons/hr
                    #         dataship.engine.ManPress = round(ManiPressure * 0.0029529983071445, 2) #In 10th of a millibar to inches of mercury to 

                    #         # Then read in a small int for each egt and cht.
                    #         for x in range(NumberOfEGT):
                    #             EGTCHTMessage = self.ser.read(2)
                    #             if(len(EGTCHTMessage)==2):
                    #                 EGTinC  = struct.unpack("<h", EGTCHTMessage)
                    #                 dataship.engine.EGT[x] = round((EGTinC[0] * 1.8) + 32) # convert from C to F
                    #         for x in range(NumberOfCHT):
                    #             EGTCHTMessage = self.ser.read(2)
                    #             if(len(EGTCHTMessage)==2):
                    #                 CHTinC  = struct.unpack("<h", EGTCHTMessage)
                    #                 dataship.engine.CHT[x] = round((CHTinC[0] * 1.8) + 32)

                    #         Checksum = self.ser.read(4) # read in last checksum part

                    #         dataship.engine.msg_count += 1
                    #         if(self.textMode_showRaw==True): dataship.engine.msg_last = binascii.hexlify(Message) # save last message.
                    #         else: dataship.engine.msg_last = None

                    else:
                        self.msg_unknown += 1 #else unknown message.
                    
                    if self.isPlaybackMode:  #if playback mode then add a delay.  Else reading a file is way to fast.
                        time.sleep(.01)
                    else:
                        pass
                        #self.ser.flushInput()  # flush the serial after every message else we see delays

                    if self.output_logFile != None:
                        Input.addToLog(self,self.output_logFile,bytearray([5,2]))
                        Input.addToLog(self,self.output_logFile,MessageHeader)
                        Input.addToLog(self,self.output_logFile,Message)

                    return dataship

                else: # bad message header found.
                    self.msg_bad += 1

            else:
                self.msg_bad += 1 #bad message found.

                return dataship
        except serial.SerialException as e:
            print(e)
            print("mgl serial exception")
            traceback.print_exc()
            dataship.errorFoundNeedToExit = True
        except Exception as e:
            print(f"Unexpected error in MGL input: {e}")
            traceback.print_exc()
            dataship.errorFoundNeedToExit = True
        return dataship
    


# vi: modeline tabstop=8 expandtab shiftwidth=4 softtabstop=4 syntax=python
