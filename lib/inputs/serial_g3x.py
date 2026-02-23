#!/usr/bin/env python

# Serial input source
# Garmin G3X
# 01/30/2019 Brian Chesteen, credit to Topher for developing template for input modules.
# 06/18/2023 C.Jones fix for live serial data input.
# 07/28/2024 A.O. grab DA and TAS from G3X Sentence ID 2 versus calculating from SID 1
# 08/06/2024 A.O. Fix SentID parsing, GPS AGL Parsing, LatLongHemi Parsing
# 11/6/2024  Added IMU data.
# 02/09/2025 DataShip refactor. Topher

from ._input import Input
from lib import hud_utils
from lib import hud_text
from lib import geomag
from . import _utils
import serial
import struct
import math, sys
import time
from contextlib import suppress
from lib.common.dataship.dataship import IMUData
from lib.common.dataship.dataship import Dataship
from lib.common.dataship.dataship_air import AirData
from lib.common.dataship.dataship_imu import IMUData
from lib.common.dataship.dataship_engine_fuel import EngineData, FuelData
from lib.common.dataship.dataship_nav import NavData
from lib.common.dataship.dataship_gps import GPSData
import traceback

def checkInputVal(value):
    try:
        newval = int(value)
        return True
    except:
        return False
    
def safeInt(value):
    try:
        newval = int(value)
        return newval
    except:
        return None

class serial_g3x(Input):
    def __init__(self):
        self.name = "serial_g3x"
        self.version = 1.2
        self.inputtype = "serial"

        # Setup moving averages to smooth a bit
        self.readings = []
        self.max_samples = 10
        self.readings1 = []
        self.max_samples1 = 20
        self.EOL = 10
        self.imuData = IMUData()
        self.airData = AirData()
        self.navData = NavData()
        self.gpsData = GPSData()
        self.engineData = EngineData()
        self.fuelData = FuelData()
        

    def initInput(self,num, dataship:Dataship):
        Input.initInput(self,num, dataship)  # call parent init Input.
        self.msg_bad = 0
        self.msg_unknown = 0
        if(self.PlayFile!=None and self.PlayFile!=False):
            # play a log file?
            self.EOL = 10 # if log file then change the EOL
            if self.PlayFile==True:
                defaultTo = "garmin_g3x_data1.txt"
                self.PlayFile = hud_utils.readConfig(self.name, "playback_file", defaultTo)
            self.ser,self.input_logFileName = Input.openLogFile(self,self.PlayFile,"r")
            self.isPlaybackMode = True
        else:
            self.EOL = 13
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
        print("G3X input init'd")

        # create a empty imu object.
        self.imuData = IMUData()
        self.imuData.id = "g3x_imu"+str(len(dataship.imuData))
        self.imuData.name = self.name
        self.imu_index = len(dataship.imuData)  # Start at 0
        dataship.imuData.append(self.imuData)
        self.last_read_time = time.time()
        print("G3X: IMU Init")

        # create a empty air object.
        self.airData = AirData()
        self.airData.id = "g3x_air"+str(len(dataship.airData))
        self.airData.name = self.name
        self.air_index = len(dataship.airData)  # Start at 0
        dataship.airData.append(self.airData)
        print("G3X: AirData Init")

        # create a empty nav object.
        self.navData = NavData()
        self.navData.id = "g3x_nav"+str(len(dataship.navData))
        self.navData.name = self.name
        self.nav_index = len(dataship.navData)  # Start at 0
        dataship.navData.append(self.navData)
        print("G3X: NavData Init")

        # create a empty gps object.
        self.gpsData = GPSData()
        self.gpsData.id = "g3x_gps"+str(len(dataship.gpsData))
        self.gpsData.name = self.name
        self.gps_index = len(dataship.gpsData)  # Start at 0
        dataship.gpsData.append(self.gpsData)
        print("G3X: GPS Data Init")

        # create a empty engine object.
        self.engineData = EngineData()
        self.engineData.id = "g3x_engine"+str(len(dataship.engineData))
        self.engineData.name = self.name
        self.engine_index = len(dataship.engineData)  # Start at 0
        dataship.engineData.append(self.engineData)
        print("G3X: Engine Data Init")


    # close this input source
    def closeInput(self, dataship:Dataship):
        if self.isPlaybackMode:
            self.ser.close()
        else:
            self.ser.close()
    

    #############################################
    ## Function: readMessage
    def readMessage(self, dataship:Dataship):
        def mean(nums):
            return float(sum(nums)) / max(len(nums), 1)
        if dataship.errorFoundNeedToExit:
            return dataship
        try:
            x = 0
            while x != 61:  # 61(=) is start of garmin g3x sentence.
                t = self.ser.read(1)
                if len(t) != 0:
                    x = ord(t)
                    if x == 64:  # 64(@) is start of garmin g3x GPS sentence.
                        msg = self.ser.read_until(expected=serial.to_bytes([10]), size=None)
                        if(dataship.debug_mode>1):
                            print("g3x: "+str(msg))

                        if(isinstance(msg,str)): msg = msg.encode() # if read from file then convert to bytes
                        #dataship.msg_last = msg
                        if len(msg) == 56:
                            UTCYear, UTCMonth, UTCDay, UTCHour, UTCMin, UTCSec, LatHemi, LatDeg, LatMin, LonHemi, LonDeg, LonMin, PosStat, HPE, GPSAlt, EWVelDir, EWVelmag, NSVelDir, NSVelmag, VVelDir, VVelmag, CRLF = struct.unpack(
                                "2s2s2s2s2s2sc2s5sc3s5sc3s6sc4sc4sc4s2s", msg
                            )
                            if CRLF[0] == self.EOL:
                                if(dataship.debug_mode>1):
                                    print("g3x: GPS Sentence")
                                self.gpsData.msg_count += 1
                                self.gpsData.sys_time_string = "%d:%d:%d"%(int(UTCHour),int(UTCMin),int(UTCSec))
                                self.gpsData.GPSTime_string = self.gpsData.sys_time_string
                                if(dataship.debug_mode>1):
                                    print("GPS Time: " + self.gpsData.GPSTime_string)
                                    current_time = time.time() # calculate hz.
                                    self.imuData.hz = round(1 / (current_time - self.last_read_time), 1)
                                    self.last_read_time = current_time
                                    print("System Time: " + str(current_time))
                                if checkInputVal(GPSAlt):
                                    self.gpsData.Alt = int(GPSAlt) * 3.28084
                                self.gpsData.EWVelDir = EWVelDir.decode('utf-8')  # E or W
                                if checkInputVal(EWVelmag):
                                    self.gpsData.EWVelmag = int(EWVelmag) * 0.1
                                self.gpsData.NSVelDir = NSVelDir.decode('utf-8')  # N or S
                                if checkInputVal(NSVelmag):
                                    self.gpsData.NSVelmag = int(NSVelmag) * 0.1
                                self.gpsData.VVelDir = VVelDir.decode('utf-8')  # U or D
                                if checkInputVal(VVelmag):
                                    self.gpsData.VVelmag = int(VVelmag) * 0.1
                                self.gpsData.Mag_Decl, self.gpsData.Lat, self.gpsData.Lon = _utils.calc_geomag(
                                    LatHemi.decode('utf-8'),
                                    int(LatDeg),
                                    int(LatMin) * 0.001,
                                    LonHemi.decode('utf-8'),
                                    int(LonDeg),
                                    int(LonMin) * 0.001,
                                )
                                #self.gpsData.GndSpeed = _utils.gndspeed(EWVelmag, NSVelmag) * 1.15078 # convert back to mph - commented due to G3X sentence already existing
                                self.gpsData.GndTrack = _utils.gndtrack(
                                    EWVelDir, EWVelmag, NSVelDir, NSVelmag
                                )
                                # dataship.wind_speed, dataship.wind_dir, dataship.norm_wind_dir = _utils.windSpdDir(
                                #     dataship.tas * 0.8689758, # back to knots.
                                #     dataship.gndspeed * 0.8689758, # convert back to knots
                                #     dataship.gndtrack,
                                #     dataship.mag_head,
                                #     dataship.mag_decl,
                                # )
                                if self.output_logFile != None:
                                    Input.addToLog(self,self.output_logFile,bytes([64]))
                                    Input.addToLog(self,self.output_logFile,msg)
                                return dataship
                            else:
                                dataship.gpsData.msg_bad += 1

                else:
                    if (self.isPlaybackMode ):  # if no bytes read and in playback mode.  then reset the file pointer to the start of the file.
                        self.ser.seek(0)

            SentID = self.ser.read(1) # get message id
            if(not isinstance(SentID,str)): SentID = SentID.decode('utf-8')
            if SentID == "1":  # atittude/air data message
                msg = self.ser.read_until(expected=serial.to_bytes([10]), size=None)
                self.imuData.msg_last = msg
                if len(msg) == 57:
                    if(dataship.debug_mode>1):
                        print("g3x: Attitude/Air Data Sentence (id:1)")
                    if(isinstance(msg,str)): msg = msg.encode() # if read from file then convert to bytes
                    SentVer, UTCHour, UTCMin, UTCSec, UTCSecFrac, Pitch, Roll, Heading, Airspeed, PressAlt, RateofTurn, LatAcc, VertAcc, AOA, VertSpeed, OAT, AltSet, Checksum, CRLF = struct.unpack(
                        "c2s2s2s2s4s5s3s4s6s4s3s3s2s4s3s3s2s2s", msg
                    )
                    if int(SentVer) == 1 and CRLF[0] == self.EOL:
                        if checkInputVal(Roll):
                            self.imuData.roll = (int(Roll) / 10) * -1
                        if checkInputVal(Pitch):
                            self.imuData.pitch = (int(Pitch) / 10)
                        if checkInputVal(Airspeed):
                            self.airData.IAS = int(Airspeed) * 0.115078 # convert knots to mph * 0.1
                        self.airData.Alt_pres = safeInt(PressAlt)
                        if checkInputVal(OAT):
                            self.airData.OAT = (int(OAT) * 1.8) + 32 # c to f
                        if _utils.is_number(AOA) == True:
                            self.airData.AOA = int(AOA)
                            self.readings1.append(self.airData.AOA)
                            self.airData.AOA = mean(
                                self.readings1
                            )  # Moving average to smooth a bit
                        else:
                            self.airData.AOA = 0
                        if len(self.readings1) == self.max_samples1:
                            self.readings1.pop(0)
                        self.imuData.mag_head = safeInt(Heading)
                        self.imuData.yaw = safeInt(Heading)
                        if checkInputVal(AltSet):
                            self.airData.Baro = (int(AltSet) + 2750.0) / 100.0
                            self.airData.Baro_diff = self.airData.Baro - 29.9213
                        if checkInputVal(PressAlt):
                            self.airData.Alt = int(
                                int(PressAlt) + (self.airData.Baro_diff / 0.00108)
                            )  # 0.00108 of inches of mercury change per foot.
                        self.airData.BALT = self.airData.Alt
                        if checkInputVal(VertSpeed):
                            self.airData.VSI = int(VertSpeed) * 10 # vertical speed in fpm
                        if checkInputVal(RateofTurn):
                            self.imuData.turn_rate = int(RateofTurn) * 0.1
                        if checkInputVal(VertAcc):
                            self.imuData.vert_G = int(VertAcc) * 0.1
                        if checkInputVal(LatAcc):
                            self.imuData.slip_skid = int(LatAcc) * 0.01
                            self.readings.append(self.imuData.slip_skid)
                            self.imuData.slip_skid = mean(
                                self.readings
                            )  # Moving average to smooth a bit
                            if len(self.readings) == self.max_samples:
                                self.readings.pop(0)
                        self.imuData.msg_count += 1
                        if (self.isPlaybackMode):  # if playback mode then add a delay.  Else reading a file is way to fast.
                            time.sleep(0.08)
                        if self.output_logFile != None:
                            Input.addToLog(self,self.output_logFile,bytes([61,ord(SentID)]))
                            Input.addToLog(self,self.output_logFile,msg)
                        # Update IMU data
                        if dataship.debug_mode > 0:
                            current_time = time.time() # calculate hz.
                            self.imuData.hz = round(1 / (current_time - self.last_read_time), 1)
                            self.last_read_time = current_time
                            print("System Time: " + str(current_time))
                            print("GPS Time: " + self.gpsData.GPSTime_string)
                        if self.output_logFile != None:
                            Input.addToLog(self,self.output_logFile,bytes([61,ord(SentID)]))
                            Input.addToLog(self,self.output_logFile,msg)
                        return dataship
                    else:
                        self.airData.msg_bad += 1
                elif len(msg) == 45:
                    if(dataship.debug_mode>1):
                        print("g3x: Attitude/Air Data Sentence")
                    if(isinstance(msg,str)): msg = msg.encode() # if read from file then convert to bytes
                    SentVer, UTCHour, UTCMin, UTCSec, UTCSecFrac, Pitch, Roll, Heading, Airspeed, PressAlt, VertSpeed, OAT, AltSet, Checksum, CRLF = struct.unpack(
                        "c2s2s2s2s4s5s3s4s6s4s3s3s2s2s", msg
                    )
                    if int(SentVer) == 1 and CRLF[0] == self.EOL:
                        if checkInputVal(Roll):
                            self.imuData.roll = (int(Roll) / 10) * -1
                        if checkInputVal(Pitch):
                            self.imuData.pitch = (int(Pitch) / 10)
                        if checkInputVal(Airspeed):
                            self.airData.IAS = int(Airspeed) * 0.115078 # convert knots to mph * 0.1
                        self.airData.Alt_pres = safeInt(PressAlt)
                        if checkInputVal(OAT):
                            self.airData.OAT = (int(OAT) * 1.8) + 32 # c to f
                        if len(self.readings1) == self.max_samples1:
                            self.readings1.pop(0)
                        self.imuData.mag_head = safeInt(Heading)
                        self.imuData.yaw = safeInt(Heading)
                        if checkInputVal(AltSet):
                            self.airData.Baro = (int(AltSet) + 2750.0) / 100.0
                            self.airData.Baro_diff = self.airData.Baro - 29.9213
                        if checkInputVal(PressAlt):
                            self.airData.Alt = int(
                                int(PressAlt) + (self.airData.Baro_diff / 0.00108)
                            )  # 0.00108 of inches of mercury change per foot.
                        self.airData.BALT = self.airData.Alt
                        if checkInputVal(VertSpeed):
                            self.airData.VSI = int(VertSpeed) * 10 # vertical speed in fpm
                        self.imuData.msg_count += 1
                        if (self.isPlaybackMode):  # if playback mode then add a delay.  Else reading a file is way to fast.
                            time.sleep(0.08)
                        if self.output_logFile != None:
                            Input.addToLog(self,self.output_logFile,bytes([61,ord(SentID)]))
                            Input.addToLog(self,self.output_logFile,msg)
                        if dataship.debug_mode > 0:
                            current_time = time.time() # calculate hz.
                            self.imuData.hz = round(1 / (current_time - self.last_read_time), 1)
                            self.last_read_time = current_time
                            print("System Time: " + str(current_time))
                            print("GPS Time: " + self.gpsData.GPSTime_string)
                        if self.output_logFile != None:
                            Input.addToLog(self,self.output_logFile,bytes([61,ord(SentID)]))
                            Input.addToLog(self,self.output_logFile,msg)
                        return dataship
                else:
                    self.airData.msg_bad += 1
            elif SentID == "2":
                msg = self.ser.read_until(expected=serial.to_bytes([10]), size=None)
                self.airData.msg_last = msg
                if len(msg) == 40:
                    if(dataship.debug_mode>1):
                        print("g3x: Attitude/Air Data Sentence (id:2) TAS, DAlt, HeadingSel, AltSel, AirspeedSel, VSSel")
                    if(isinstance(msg,str)): msg = msg.encode() # if read from file then convert to bytes
                    SentVer, UTCHour, UTCMin, UTCSec, UTCSecFrac, TAS, DAlt, HeadingSel, AltSel, AirspeedSel, VSSel, Checksum, CRLF = struct.unpack(
                        "c2s2s2s2s4s6s3s6s4s4s2s2s", msg
                    )
                    if int(SentVer) == 1 and CRLF[0] == self.EOL:
                        self.airData.Alt_da = safeInt(DAlt)
                        if checkInputVal(TAS):
                            self.airData.TAS = int(TAS) * 0.115078 # convert knots to mph * 0.1
                        self.navData.HeadBug = safeInt(HeadingSel)
                        self.navData.AltBug = safeInt(AltSel)
                        if checkInputVal(AirspeedSel):
                            self.navData.ASIBug = int(AirspeedSel) * 0.115078 # convert knots to mph * 0.1
                        if checkInputVal(VSSel):
                            self.navData.VSBug = int(VSSel) * 10 # multiply up to hundreds of feet
                        self.navData.msg_count += 1
                        if (self.isPlaybackMode):  # if playback mode then add a delay.  Else reading a file is way to fast.
                            time.sleep(0.08)

                        if self.output_logFile != None:
                            Input.addToLog(self,self.output_logFile,bytes([61,ord(SentID)]))
                            Input.addToLog(self,self.output_logFile,msg)
                        return dataship
                    else:
                        self.airData.msg_bad += 1
                elif len(msg) == 28:
                    if(dataship.debug_mode>1):
                        print("g3x: Attitude/Air Data Sentence (id:2) TAS")
                    if(isinstance(msg,str)): msg = msg.encode() # if read from file then convert to bytes
                    SentVer, UTCHour, UTCMin, UTCSec, UTCSecFrac, TAS, unknownvalue, Checksum, CRLF = struct.unpack(
                        "c2s2s2s2s4s11s2s2s", msg
                    )
                    if int(SentVer) == 1 and CRLF[0] == self.EOL:
                        if checkInputVal(TAS):
                            self.airData.TAS = int(TAS) * 0.115078 # convert knots to mph * 0.1
                        self.airData.msg_count += 1
                        if (self.isPlaybackMode):  # if playback mode then add a delay.  Else reading a file is way to fast.
                            time.sleep(0.08)
                        if self.output_logFile != None:
                            Input.addToLog(self,self.output_logFile,bytes([61,ord(SentID)]))
                            Input.addToLog(self,self.output_logFile,msg)
                        return dataship
                else:
                    self.airData.msg_bad += 1
            elif SentID == "7":  # GPS AGL data message
                msg = self.ser.read_until(expected=serial.to_bytes([10]), size=None)
                if(isinstance(msg,str)): msg = msg.encode() # if read from file then convert to bytes
                #dataship.msg_last = msg
                if len(msg) == 20:
                    if(dataship.debug_mode>1):
                        print("g3x: GPS AGL data message")
                    msg = (msg[:20]) if len(msg) > 20 else msg
                    SentVer, UTCHour, UTCMin, UTCSec, UTCSecFrac, HeightAGL, GroundSpeed, Checksum, CRLF = struct.unpack(
                        "c2s2s2s2s3s4s2s2s", msg
                    )
                    if int(SentVer) == 1 and CRLF[0] == self.EOL:
                        if checkInputVal(HeightAGL):
                            self.airData.Alt_agl = int(HeightAGL) * 100
                        if checkInputVal(GroundSpeed):
                            self.gpsData.GndSpeed = int(GroundSpeed) * 0.115078 # convert knots to mph * 0.1
                        self.gpsData.msg_count += 1
                        if self.output_logFile != None:
                            Input.addToLog(self,self.output_logFile,bytes([61,ord(SentID)]))
                            Input.addToLog(self,self.output_logFile,msg)
                        return dataship
                    else:
                        self.airData.msg_bad += 1

                else:
                    self.airData.msg_bad += 1
                    if(dataship.debug_mode>1):
                        print("g3x: unknown message")
            else:
                self.msg_unknown += 1  # else unknown message.
                if self.isPlaybackMode:
                    time.sleep(0.01)
                else:
                    self.ser.flushInput()  # flush the serial after every message else we see delays
                return dataship

            #The following commented out due to lack of testing. To be re-integrated in following further testing
            '''elif SentID == "3":  # Engine Data Message
                msg = self.ser.read_until(expected=serial.to_bytes([10]), size=None)
                if(isinstance(msg,str)): msg = msg.encode() # if read from file then convert to bytes
                #dataship.msg_last = msg
                if len(msg) == 219:
                    msg = (msg[:219]) if len(msg) > 219 else msg
                    SentVer, UTCHour, UTCMin, UTCSec, UTCSecFrac, OilP, OilT, RPM, unused, MAP, FF, FuelP, FQtyL, FQtyR, CalcFuel, Volt1, Volt2, Amp1, Hobbs, Tach, CHT6, EGT6, CHT5, EGT5, CHT4, EGT4, CHT3, EGT3, CHT2, EGT2, CHT1, EGT1, TIT1, TIT2, ElevTrim, ElevTrimUnit, FlapPos, FlapPosUnit, CarbTemp, CarbTempUnit, CoolantPress, CoolantPressUnit, CoolantTemp, CoolantTempUnit, Amps2, Amps2Unit, AilTrim, AilTrimUnit, RudTrim, RudTrimUnit, FuelQtyLAux, FuelQtyLAuxUnit, FuelQtyRAux, FuelQtyRAuxUnit, Unused2, Disc1, Disc2, Disc3, Disc4, Unused3, Checksum, CRLF = struct.unpack(
                        "c2s2s2s2s3s4s4s4s3s3s3s3s3s3s3s3s3s4s5s5s4s4s4s4s4s4s4s4s4s4s4s4s4s4s5sc5sc5sc5sc5sc5sc5sc5sc5sc5sc18scccc12s2s2s", msg
                    )
                    if int(SentVer) == 1 and CRLF[0] == self.EOL:
                        #Still need: EGT, CHT
                        if checkInputVal(MAP):
                            self.engineData.ManPress = (int(MAP) * .1) / 2.036
                        if checkInputVal(CoolantTemp):
                            self.engineData.CoolantTemp = ((int(CoolantTemp) * .1) * 1.8) + 32
                        if checkInputVal(FF):
                            self.engineData.FuelFlow = (int(FF) * .1)
                        if checkInputVal(FuelP):
                            self.engineData.FuelPress = (int(FuelP) * .1)
                        if checkInputVal(Volt1):
                            self.engineData.volts1 = (int(Volt1) * .1)
                        if checkInputVal(Volt2):
                            self.engineData.volts2 = (int(Volt2) * .1)
                        if checkInputVal(Amp1):
                            self.engineData.amps = (int(Amp1) * .1)
                        self.engineData.OilTemp = (safeInt(OilT) * 1.8) + 32
                        self.engineData.RPM = safeInt(RPM)
                        self.engineData.OilPress = safeInt(OilP)
                        self.engineData.hobbs_time = safeInt(Hobbs) * .1
                        self.engineData.tach_time = safeInt(Tach) * .1
                        self.fuelData.FuelRemain = safeInt(CalcFuel) * .1
                        fuelqty1 = safeInt(FQtyL)
                        fuelqty2 = safeInt(FQtyR)
                        fuelqty3, fuelqty4 = 0
                        if checkInputVal(FuelQtyLAux):
                            fuelqty3 = int(FuelQtyLAux) * .1
                        if checkInputVal(FuelQtyRAux):
                            fuelqty4 = int(FuelQtyRAux) * .1
                        self.fuelData.FuelLevels = [fuelqty1,fuelqty2,fuelqty3,fuelqty4]
                        self.engineData.msg_count = +1
                        return dataship
                    else:
                        self.airData.msg_bad += 1

                else:
                    self.airData.msg_bad += 1'''

        except Exception as e:
            print("G3X serial exception")
            print(type(e))
            print(e)
            traceback.print_exc()
            dataship.errorFoundNeedToExit = True

        return dataship




# vi: modeline tabstop=8 expandtab shiftwidth=4 softtabstop=4 syntax=python
