#!/usr/bin/env python

# Serial input source
# Skyview
# 1/23/2019  Topher
# 11/6/2024  Added IMU data
# 11/30/2024 Added NAV, Autopilot and EMS data   Zap
# 2/9/2025   Dataship refactor

from ._input import Input
from lib import hud_utils
import serial
import time
from lib.common.dataship.dataship_imu import IMUData
from lib.common.dataship.dataship import Dataship
from lib.common.dataship.dataship_nav import NavData
from lib.common.dataship.dataship_engine_fuel import EngineData, FuelData
from lib.common.dataship.dataship_gps import GPSData
from lib.common.dataship.dataship_air import AirData
import struct  # Add this import at the top with other imports

class serial_skyview(Input):
    def __init__(self):
        self.name = "serial_skyview"
        self.version = 1.0
        self.inputtype = "serial"
        self.EOL = 10
        self.imuData = IMUData()
        self.navData = NavData()
        self.engineData = EngineData()
        self.fuelData = FuelData()
        self.gpsData = GPSData()
        self.airData = AirData()
        self.msg_unknown = 0
        self.msg_bad = 0
        self.nmea_buffer = ""  # Add buffer for NMEA messages

    def initInput(self,num,dataship: Dataship):
        Input.initInput( self,num, dataship )  # call parent init Input.
        
        if(self.PlayFile!=None and self.PlayFile!=False):
            # load playback file.
            if self.PlayFile==True:
                defaultTo = "dynon_skyview_data2.txt"
                self.PlayFile = hud_utils.readConfig(self.name, "playback_file", defaultTo)
            self.ser,self.input_logFileName = Input.openLogFile(self,self.PlayFile,"r")
            self.isPlaybackMode = True
        else:
            self.efis_data_format = hud_utils.readConfig(self.name, "format", "none")
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
                timeout=1
            )

        # create a empty imu object.
        self.imuData = IMUData()
        self.imuData.name = "skyview_imu"
        self.imu_index = len(dataship.imuData)  # Start at 0
        self.imuData.id = "skyview_imu"+str(self.imu_index)
        dataship.imuData.append(self.imuData)
        self.last_read_time = time.time()

        # create a empty nav object.
        self.navData = NavData()
        self.navData.name = "skyview_nav"
        self.navData.id = "skyview_nav"+str(len(dataship.navData))
        dataship.navData.append(self.navData)

        # create a empty engine object.
        self.engineData = EngineData()
        self.engineData.name = "skyview_engine"
        self.engineData.id = "skyview_engine"+str(len(dataship.engineData))
        dataship.engineData.append(self.engineData)

        # create a empty fuel object.
        self.fuelData = FuelData()
        self.fuelData.name = "skyview_fuel"
        self.fuelData.id = "skyview_fuel"+str(len(dataship.fuelData))
        dataship.fuelData.append(self.fuelData)

        # create a empty gps object.
        self.gpsData = GPSData()
        self.gpsData.name = "skyview_gps"
        self.gpsData.id = "skyview_gps"+str(len(dataship.gpsData))
        dataship.gpsData.append(self.gpsData)

        # create a empty air object.
        self.airData = AirData()
        self.airData.name = "skyview_air"
        self.airData.id = "skyview_air"+str(len(dataship.airData))
        dataship.airData.append(self.airData)

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
            # Read until we find a message start character ($ or !)
            x = 0
            while x != 33 and x != ord('$'):  # Look for ! (33) or $ start characters
                t = self.ser.read(1)
                if len(t) != 0:
                    x = ord(t)
                else:
                    if self.isPlaybackMode:  # if no bytes read and in playback mode, reset file pointer
                        self.ser.seek(0)
                    return dataship

            # Found a start character - handle NMEA or Skyview message
            if x == ord('$'):  # NMEA message
                nmea_msg = bytes([x]) + self.ser.readline()
                try:
                    # Parse NMEA message
                    fields = nmea_msg.decode().strip().split(',')
                    sentence = fields[0]

                    if sentence == "$GPGGA" and len(fields) >= 11 and fields[2] and fields[4]:
                        # Update position
                        lat_str, lat_hem = fields[2], fields[3]
                        lon_str, lon_hem = fields[4], fields[5]
                        
                        # Convert latitude
                        degrees = float(lat_str[:2])
                        minutes = float(lat_str[2:])
                        self.gpsData.Lat = -(degrees + minutes/60) if lat_hem == 'S' else (degrees + minutes/60)
                        
                        # Convert longitude 
                        degrees = float(lon_str[:3])
                        minutes = float(lon_str[3:])
                        self.gpsData.Lon = -(degrees + minutes/60) if lon_hem == 'W' else (degrees + minutes/60)
                        
                        self.gpsData.Alt = float(fields[9]) if fields[9] else 0
                        self.gpsData.SatsTracked = int(fields[7]) if fields[7] else 0
                        
                    elif sentence == "$GPGSA" and len(fields) >= 18:
                        pass
                        
                    elif sentence == "$GPRMC" and len(fields) >= 12 and fields[3] and fields[5]:
                        lat_str, lat_hem = fields[3], fields[4]
                        lon_str, lon_hem = fields[5], fields[6]
                        
                        # Convert latitude
                        degrees = float(lat_str[:2])
                        minutes = float(lat_str[2:])
                        self.gpsData.Lat = -(degrees + minutes/60) if lat_hem == 'S' else (degrees + minutes/60)
                        
                        # Convert longitude
                        degrees = float(lon_str[:3])
                        minutes = float(lon_str[3:])
                        self.gpsData.Lon = -(degrees + minutes/60) if lon_hem == 'W' else (degrees + minutes/60)
                        
                        self.gpsData.GndSpeed = float(fields[7])*1.15078 if fields[7] else 0  # Convert knots to mph
                        self.gpsData.GndTrack = float(fields[8]) if fields[8] else 0
                        
                    elif sentence == "$GPVTG" and len(fields) >= 8:
                        self.gpsData.GndTrack = float(fields[1]) if fields[1] else 0
                        self.gpsData.GndSpeed = float(fields[5])*0.621371 if fields[5] else 0  # Convert km/h to mph
                        
                    elif sentence == "$GPGSV" and len(fields) >= 4:
                        self.gpsData.SatsVisible = int(fields[3]) if fields[3] else 0

                    self.gpsData.msg_count += 1
                except:
                    self.gpsData.msg_bad += 1

                if self.output_logFile != None:
                    #write the nmea message to the log file. write out the start character, then the message.
                    Input.addToLog(self,self.output_logFile,bytes([ord('$')]))
                    Input.addToLog(self,self.output_logFile,nmea_msg)

                return dataship

            # Must be Skyview message (x == 33)
            dataType = self.ser.read(1)
            dataVer = self.ser.read(1)

            if isinstance(dataType,str):
                dataType = dataType.encode() # if read from file then convert to bytes
                dataVer = dataVer.encode()

            if True:
                #msg = (msg[:73]) if len(msg) > 73 else msg
                #aircraft.msg_last = msg
                if dataType == b'1':  # AHRS message
                    msg = self.ser.read(71)
                    if(isinstance(msg,str)): msg = msg.encode() # if read from file then convert to bytes
                    HH, MM, SS, FF, pitch, roll, HeadingMAG, IAS, PresAlt, TurnRate, LatAccel, VertAccel, AOA, VertSpd, OAT, TAS, Baro, DA, WD, WS, Checksum, CRLF = struct.unpack(
                         # Format string breakdown:
                         # 8s - System time (8 bytes)
                         # 4s - Pitch (4 bytes)
                         # 5s - Roll  (5 bytes)
                         # 3s - Heading  (3 bytes)
                         # 4s - IAS (4 bytes)
                         # 6s - Pres Alt (6 bytes)
                         # 4s - Turn Rate (4 bytes)
                         # 3s - Lat Accel (3 bytes)
                         # 3s - Vert Accel (3 bytes)
                         # 2s - AOA (2 bytes)
                         # 4s - Vertical Speed (4 bytes)
                         # 3s - OAT (3 bytes)
                         # 4s - TAS (4 bytes)
                         # 3s - Baro Setting (3 bytes)
                         # 6s - Density Altitude (6 bytes)
                         # 3s - Wind Direction (3 bytes)
                         # 2s - Wind Speed (2 bytes)
                         # 2s - Checksum (2 bytes)
                         # 2s - CRLF (2 bytes)                            
                        "2s2s2s2s4s5s3s4s6s4s3s3s2s4s3s4s3s6s3s2s2s2s", msg
                    ) 
                    #print(msg)
                    if HH != b'--' and MM != b'--' and SS != b'--':
                        self.gpsData.GPSTime_string = "%d:%d:%d"%(int(HH),int(MM),int(SS))
                        self.time_stamp_string = dataship.sys_time_string
                        #print("time: "+aircraft.sys_time_string)
                        
                    self.imuData.pitch = Input.cleanInt(self,pitch) / 10
                    self.imuData.roll = Input.cleanInt(self,roll) / 10
                    self.imuData.mag_head = Input.cleanInt(self,HeadingMAG)

                    # Update IMU data
                    self.imuData.yaw = self.imuData.mag_head
                    if dataship.debug_mode > 0:
                        current_time = time.time() # calculate hz.
                        self.imuData.hz = round(1 / (current_time - self.last_read_time), 1)
                        self.last_read_time = current_time

                    self.airData.IAS = Input.cleanInt(self,IAS) * 0.1
                    self.airData.Alt_pres = Input.cleanInt(self,PresAlt)
                    if OAT != b'XXX': self.airData.OAT = (Input.cleanInt(self,OAT) * 1.8) + 32 # c to f
                    if TAS != b'XXXX': self.airData.TAS = Input.cleanInt(self,TAS) * 0.1
                    if AOA == b'XX':
                        self.airData.AOA = 0
                    else:
                        self.airData.AOA = Input.cleanInt(self,AOA)
                    self.airData.Baro = (Input.cleanInt(self,Baro) + 2750.0) / 100
                    self.airData.Baro_diff = self.airData.Baro - 29.921
                    if DA != b'XXXXXX': self.airData.Alt_da = Input.cleanInt(self,DA)
                    self.airData.Alt = int( Input.cleanInt(self,PresAlt) + (self.airData.Baro_diff / 0.00108) )  # 0.00108 of inches of mercury change per foot.
                    self.imuData.turn_rate = Input.cleanInt(self,TurnRate) * 0.1
                    self.airData.VSI = Input.cleanInt(self,VertSpd) * 10
                    self.imuData.vert_G = Input.cleanInt(self,VertAccel) * 0.1
                    try:
                        self.airData.Wind_dir = Input.cleanInt(self,WD)
                        self.airData.Wind_speed = Input.cleanInt(self,WS)
                        self.airData.Wind_dir_corr = (self.imuData.mag_head - self.airData.Wind_dir) % 360 #normalize the wind direction to the airplane heading
                        # # compute Gnd Speed when Gnd Speed is unknown (not provided in data)
                        # dataship.gndspeed = math.sqrt(math.pow(dataship.tas,2) + math.pow(dataship.wind_speed,2) + (2 * dataship.tas * dataship.wind_speed * math.cos(math.radians(180 - (dataship.wind_dir - dataship.mag_head)))))
                        # dataship.gndtrack = dataship.mag_head 
                    except ValueError as ex:
                        # if error trying to parse wind then must not have that info.
                        self.airData.Wind_dir = None
                        self.airData.Wind_speed = None
                        self.airData.Wind_dir_corr = None #normalize the wind direction to the airplane heading

                    self.airData.msg_count += 1
                    self.imuData.msg_count += 1

                    if self.output_logFile != None:
                        Input.addToLog(self,self.output_logFile,bytes([33,int(dataType),int(dataVer)]))
                        Input.addToLog(self,self.output_logFile,msg)

                elif dataType == b'2': #Dynon System message (nav,AP, etc)
                    self.navData.msg_count += 1
                    msg = self.ser.read(90)
                    if isinstance(msg, str): msg = msg.encode()  # if read from file then convert to bytes
                    HH,MM,SS,FF,HBug,AltBug, ASIBug,VSBug,Course,CDISrcType,CDISourePort,CDIScale,CDIDeflection,GS,APEng,APRollMode,Not1,APPitch,Not2,APRollF,APRollP,APRollSlip,APPitchF, APPitchP,APPitchSlip,APYawF,APYawP,APYawSlip,TransponderStatus,TransponderReply,TransponderIdent,TransponderCode,DynonUnused,Checksum,CRLF= struct.unpack(
                         # Format string breakdown:
                         # 8s - System time (8 bytes)
                         # 3s - Heading bug (3 bytes)
                         # 5s - Altitude bug (5 bytes)
                         # 4s - Airspeed bug (4 bytes)
                         # 4s - Vertical speed bug (4 bytes)
                         # 3s - Course (3 bytes)
                         # c  - CDI source type (1 byte)
                         # c  - CDI source port (1 byte)
                         # 2s - CDI scale (2 bytes)
                         # 3s - CDI deflection (3 bytes)
                         # 3s - Glide slope % (3 bytes)
                         # c  - Autopilot engaged (1 byte)
                         # c  - AP roll mode (1 byte)
                         # c  - Not used (1 byte)
                         # c  - AP pitch mode (1 byte)
                         # c  - Not used (1 byte)
                         # 3s - AP roll force (3 bytes)
                         # 5s - AP roll position (5 bytes)
                         # c  - AP roll slip (1 byte)
                         # 3s - AP pitch force (3 byte)
                         # 5s - AP pitch position (5 bytes)
                         # c  - AP pitch slip (1 byte)
                         # 3s - AP yaw force (3 bytes)
                         # 5s - AP yaw position (5 bytes)
                         # c  - AP yaw slip (1 byte)
                         # c  - Transponder status (1 byte)
                         # c  - Transponder reply (1 byte)
                         # c  - Transponder Ident (1 byte)
                         # 4s - Transponder code (4 bytes)
                         # 10s- Not used (10 bytes)
                         # 2s - Checksum (2 bytes)
                         # 2s - CRLF (2 bytes)
                        "2s2s2s2s3s5s4s4s3scc2s3s3sccccc3s5sc3s5sc3s5scccc4s10s2s2s", msg
                    )
                    #print("NAV & System Message !2:", msg)
                    if HH != b'--' and MM != b'--' and SS != b'--':
                        self.gpsData.GPSTime_string = "%d:%d:%d"%(int(HH),int(MM),int(SS))
                        self.time_stamp_string = self.gpsData.GPSTime_string

                    if HBug != b'XXX': self.navData.HeadBug = Input.cleanInt(self, HBug)
                    if AltBug != b'XXXXX': self.navData.AltBug = Input.cleanInt(self,AltBug) * 10
                    if ASIBug != b'XXXX': self.navData.ASIBug = Input.cleanInt(self,ASIBug) / 10
                    if VSBug != b'XXXX': self.navData.VSBug = Input.cleanInt(self,VSBug) / 10
                    if CDIDeflection != b'XXX': self.navData.ILSDev = Input.cleanInt(self,CDIDeflection)
                    if GS != b'XXX': self.navData.GSDev = Input.cleanInt(self,GS)
                    self.navData.HSISource = Input.cleanInt(self,CDISourePort)
                    if CDISrcType == b'0':
                        navSourceType = 'GPS'
                    elif CDISrcType == b'1':
                        navSourceType = 'NAV'
                    elif CDISrcType == b'2':
                        navSourceType = 'LOC'
                    self.navData.SourceDesc = navSourceType + str(Input.cleanInt(self,CDISourePort))
                    if CDIScale != b'XX': self.navData.GLSHoriz = Input.cleanInt(self,CDIScale) / 10
                    if APEng == b'0': self.navData.APeng = 0
                    if APEng == b'1' or APEng == b'2' or APEng == b'3' or APEng == b'4' or APEng == b'5' or APEng == b'6' or APEng == b'7': self.navData.APeng = 1
                    self.navData.AP_RollForce = Input.cleanInt(self,APRollF)
                    if APRollP != 'XXXXX': self.navData.AP_RollPos = Input.cleanInt(self,APRollP)
                    self.navData.AP_RollSlip = Input.cleanInt(self,APRollSlip)
                    self.navData.AP_PitchForce = Input.cleanInt(self,APPitchF)
                    if APPitchP != b'XXXXX': self.navData.AP_PitchPos = Input.cleanInt(self,APPitchP)
                    self.navData.AP_PitchSlip = Input.cleanInt(self,APPitchSlip)
                    self.navData.AP_YawForce = Input.cleanInt(self,APYawF)
                    if APYawP != b'XXXXX': self.navData.AP_YawPos = Input.cleanInt(self,APYawP)
                    self.navData.AP_YawSlip = Input.cleanInt(self,APYawSlip)
                    if TransponderStatus == b'X':
                        dataship.nav.XPDR_Status = 'OFF'
                    elif TransponderStatus == b'0':
                        self.navData.XPDR_Status = 'SBY'
                    elif TransponderStatus == b'1':
                        self.navData.XPDR_Status = 'GND'
                    elif TransponderStatus == b'2':
                        self.navData.XPDR_Status = 'ON'
                    elif TransponderStatus == b'3':
                        self.navData.XPDR_Status = 'ALT'
                    if TransponderReply != b'X': self.navData.XPDR_Reply = Input.cleanInt(self,TransponderReply)
                    if TransponderIdent != b'X': self.navData.XPDR_Ident = Input.cleanInt(self,TransponderIdent)
                    if TransponderCode != b'XXXX': self.navData.XPDR_Code = Input.cleanInt(self,TransponderCode)
                    
                    if self.output_logFile != None:
                        Input.addToLog(self,self.output_logFile,bytes([33,int(dataType),int(dataVer)]))
                        Input.addToLog(self,self.output_logFile,msg)

                elif dataType == b'3': #Dynon EMS Engine data message
                    self.engineData.msg_count += 1
                    msg = self.ser.read(222)
                    if isinstance(msg,str):msg = msg.encode() # if read from file then convert to bytes
                    HH,MM,SS,FF,OilPress,OilTemp, RPM_L,RPM_R,MAP,FF1,FF2,FP,FL_L,FL_R,Frem,V1,V2,AMPs,Hobbs,Tach,TC1,TC2,TC3,TC4,TC5,TC6,TC7,TC8,TC9,TC10,TC11,TC12,TC13,TC14,GP1,GP2,GP3,GP4,GP5,GP6,GP7,GP8,GP9,GP10,GP11,GP12,GP13,Contacts,Pwr,EGTstate,Checksum,CRLF= struct.unpack(
                                                  # First part - Engine parameters (47 bytes total):
                         # 8s - System time (8 bytes)
                         # 3s - Oil pressure (3 bytes)
                         # 4s - Oil temperature (4 bytes)
                         # 4s - Left RPM (4 bytes)
                         # 4s - Right RPM (4 bytes)
                         # 3s - Manifold pressure (3 bytes)
                         # 3s - Fuel flow 1 (3 bytes)
                         # 3s - Fuel flow 2 (3 bytes)
                         # 3s - Fuel pressure (3 bytes)
                         # 3s - Left fuel quantity (3 bytes)
                         # 3s - Right fuel quantity (3 bytes)
                         # 3s - Fuel remaining (3 bytes)
                         # 3s - Voltage 1 (3 bytes)
                         # 3s - Voltage 2 (3 bytes)
                         # 4s - Amperage (4 bytes)
                         # 5s - Hobbs time (5 bytes)
                         # 5s - Tach time (5 bytes)
                         # 14 Thermocouples, each 4 bytes:
                         # 4s - Thermocouple 1 (4 bytes)
                         # 4s - Thermocouple 2 (4 bytes)
                         # 4s - Thermocouple 3 (4 bytes)
                         # 4s - Thermocouple 4 (4 bytes)
                         # 4s - Thermocouple 5 (4 bytes)
                         # 4s - Thermocouple 6 (4 bytes)
                         # 4s - Thermocouple 7 (4 bytes)
                         # 4s - Thermocouple 8 (4 bytes)
                         # 4s - Thermocouple 9 (4 bytes)
                         # 4s - Thermocouple 10 (4 bytes)
                         # 4s - Thermocouple 11 (4 bytes)
                         # 4s - Thermocouple 12 (4 bytes)
                         # 4s - Thermocouple 13 (4 bytes)
                         # 4s - Thermocouple 14 (4 bytes)
                         # Second part - General purpose inputs and status:
                         # 6s- General purpose input 1 (6 bytes)
                         # 6s- General purpose input 2 (6 bytes)
                         # 6s- General purpose input 3 (6 bytes)
                         # 6s- General purpose input 4 (6 bytes)
                         # 6s- General purpose input 5 (6 bytes)
                         # 6s- General purpose input 6 (6 bytes)
                         # 6s- General purpose input 7 (6 bytes)
                         # 6s- General purpose input 8 (6 bytes)
                         # 6s- General purpose input 9 (6 bytes)
                         # 6s- General purpose input 10 (6 bytes)
                         # 6s- General purpose input 11 (6 bytes)
                         # 6s- General purpose input 12 (6 bytes)
                         # 6s- General purpose input 13 (6 bytes)
                         # 16c- Contact inputs status (Not Used) (16 bytes)
                         # 3s - Power percentage (3 bytes)
                         # 2s - Checksum (2 bytes)
                         "2s2s2s2s3s4s4s4s3s3s3s3s3s3s3s3s3s4s5s5s4s4s4s4s4s4s4s4s4s4s4s4s4s4s6s6s6s6s6s6s6s6s6s6s6s6s6s16s3s1s2s2s", msg
                    )
                    #print("EMS Message !3:", msg)

                    if HH != b'--' and MM != b'--' and SS != b'--':
                        self.gpsData.GPSTime_string = "%d:%d:%d"%(int(HH),int(MM),int(SS))
                        self.time_stamp_string = self.gpsData.GPSTime_string

                    if OilPress != b'XXX': self.engineData.OilPress = Input.cleanInt(self,OilPress)
                    if OilTemp != b'XXXX': self.engineData.OilTemp = Input.cleanInt(self,OilTemp)
                    self.engineData.RPM = max(Input.cleanInt(self,RPM_L), Input.cleanInt(self,RPM_R))
                    if MAP != b'XXX': self.engineData.ManPress = Input.cleanInt(self,MAP) / 10
                    self.engineData.FuelFlow = Input.cleanInt(self,FF1) / 10
                    self.engineData.FuelFlow2 = Input.cleanInt(self,FF2) / 10
                    if FP != b'XXX': self.engineData.FuelPress = Input.cleanInt(self,FP) / 10
                    fuel_level_left  = Input.cleanInt(self, FL_L) / 10
                    fuel_level_right = Input.cleanInt(self, FL_R) / 10
                    self.fuelData.FuelLevels = [fuel_level_left, fuel_level_right, 0, 0]
                    self.fuelData.FuelRemain = Input.cleanInt(self,Frem) / 10
                    self.engineData.volts1 = Input.cleanInt(self,V1) / 10
                    self.engineData.volts2 = Input.cleanInt(self,V2) / 10
                    if AMPs != b'XXXX': self.engineData.amps = Input.cleanInt(self,AMPs) / 10
                    self.engineData.hobbs_time = Input.cleanInt(self,Hobbs) / 10
                    self.engineData.tach_time = Input.cleanInt(self,Tach) / 10

                    if TC12 != b'XXXX': self.engineData.EGT[0] = round(((Input.cleanInt(self, TC12)) * 1.8) + 32)  # convert from C to F
                    if TC10 != b'XXXX': self.engineData.EGT[1] = round(((Input.cleanInt(self, TC10)) * 1.8) + 32)  # convert from C to F
                    if TC8 != b'XXXX': self.engineData.EGT[2] = round(((Input.cleanInt(self, TC8)) * 1.8) + 32)  # convert from C to F
                    if TC6 != b'XXXX': self.engineData.EGT[3] = round(((Input.cleanInt(self, TC6)) * 1.8) + 32)  # convert from C to F
                    if TC4 != b'XXXX': self.engineData.EGT[4] = round(((Input.cleanInt(self, TC4)) * 1.8) + 32)  # convert from C to F
                    if TC2 != b'XXXX': self.engineData.EGT[5] = round(((Input.cleanInt(self, TC2)) * 1.8) + 32)  # convert from C to F

                    if TC11 != b'XXXX': self.engineData.CHT[0] = round(((Input.cleanInt(self, TC11)) * 1.8) + 32)  # convert from C to F
                    if TC9 != b'XXXX': self.engineData.CHT[1] = round(((Input.cleanInt(self, TC9)) * 1.8) + 32)  # convert from C to F
                    if TC7 != b'XXXX': self.engineData.CHT[2] = round(((Input.cleanInt(self, TC7)) * 1.8) + 32)  # convert from C to F
                    if TC5 != b'XXXX': self.engineData.CHT[3] = round(((Input.cleanInt(self, TC5)) * 1.8) + 32)  # convert from C to F
                    if TC3 != b'XXXX': self.engineData.EGT[4] = round(((Input.cleanInt(self, TC3)) * 1.8) + 32)  # convert from C to F
                    if TC1 != b'XXXX': self.engineData.EGT[5] = round(((Input.cleanInt(self, TC1)) * 1.8) + 32)  # convert from C to F

                    if self.output_logFile != None:
                        Input.addToLog(self,self.output_logFile,bytes([33,int(dataType),int(dataVer)]))
                        Input.addToLog(self,self.output_logFile,msg)
                else:
                    self.msg_unknown += 1 # unknown message found.
        except ValueError:
            self.msg_bad += 1
            #print("bad:"+str(msg))
            pass
        except struct.error:
            self.msg_bad += 1
            pass
        except serial.serialutil.SerialException:
            print("skyview serial exception")
            traceback.print_exc()
            dataship.errorFoundNeedToExit = True

        if self.isPlaybackMode:  #if play back mode then add a delay.  Else reading a file is way to fast.
            time.sleep(.05)
        else:
            #pass
            self.ser.flushInput()  # flush the serial after every message else we see delays

        return dataship

# vi: modeline tabstop=8 expandtab shiftwidth=4 softtabstop=4 syntax=python
