#!/usr/bin/env python

import math, os, sys, random
import configparser
import importlib
import shutil
from configupdater import ConfigUpdater

#############################################
## Function: readConfig
# load config.cfg file if it exists.
# set comment_prefixes to '/' and allow_no_value to True so that comments will not be removed.
configParser: configparser.ConfigParser = configparser.ConfigParser()
_config_path = "config.cfg"
if not os.path.exists(_config_path):
    _example_path = "config_example.cfg"
    if os.path.exists(_example_path):
        shutil.copy2(_example_path, _config_path)
        print(f"config.cfg not found. Copied config_example.cfg to config.cfg")
    else:
        print(f"ERROR: config.cfg not found and config_example.cfg is missing. Cannot create config.cfg")
        sys.exit(1)
if not os.access(_config_path, os.R_OK):
    print(f"ERROR: config.cfg exists but is not readable. Check file permissions.")
    sys.exit(1)
else:
    configParser.read(_config_path)

def readConfig(section, name, defaultValue=0, show_error=False,hideoutput=True) -> str:
    """
    Read a configuration value from the config.cfg file.

    Parameters
    ----------
    section : str
    name : str
    defaultValue : str
    show_error : bool
    hideoutput : bool

    Returns
    -------
    str
    """
    global configParser
    try:
        value = configParser.get(section, name)
        if(hideoutput==False): print("Config.cfg: ["+section+"] "+name+": "+value)
        return value
    except Exception as e:
        if show_error == True:
            print(("config value not set section: ", section, " key:", name, " -- not found"))
            print(e)
        return defaultValue


#############################################
## Function: readConfigInt
def readConfigInt(section, name, defaultValue=0):
    return int(readConfig(section, name, defaultValue=defaultValue))

#############################################
## Function: readConfigBool
def readConfigBool(section, name, defaultValue=False):
    theValue = readConfig(section, name, defaultValue=defaultValue)
    if(type(theValue) == type(True)): return theValue
    if(isinstance(theValue, str)): 
        if(theValue.upper()=="TRUE"): return True
        if(theValue.upper()=="FALSE"): return False
    # else return default value.
    return defaultValue


#############################################
## Function: writeConfig
def writeConfig(section, name, value):
    """
    Write a configuration value to the config.cfg file.

    Parameters
    ----------
    section : str
    name : str
    value : str
    """

    # check if the config.cfg file exists
    if not os.path.exists("config.cfg"):
        print("config.cfg file not found. creating from config_example.cfg")
        shutil.copy("config_example.cfg", "config.cfg")
        # reload the config
        configParser.read("config.cfg")
    
    updater = ConfigUpdater()
    updater.read("config.cfg")
    updater[section][name] = value
    with open("config.cfg", "w") as f:
        updater.write(f)
    print(f"Config.cfg: [{section}] {name}: {value}")


#############################################
## Function: get_bin
# https://stackoverflow.com/questions/699866/python-int-to-binary#699891
def get_bin(x, n=8):
    """
    Get the binary representation of x.

    Parameters
    ----------
    x : int
    n : int
        Minimum number of digits. If x needs less digits in binary, the rest
        is filled with zeros.

    Returns
    -------
    str
    """
    return format(x, "b").zfill(n)


##############################################
## function: getLogDataFiles()
## return list of log files in standard dir and in user defined dir.
def getLogDataFiles(showErrorIfNoUSB=False):
    from lib.common import shared
    from lib.util import rpi_hardware

    extraPath = readConfig("DataRecorder", "path", shared.DefaultFlightLogDir)
    files = []
    extrafiles = []
    usbfiles = []
    # list files in inputs example folder.
    lst = os.listdir("lib/inputs/_example_data")
    for d in lst:
        if not d.startswith("_"):
            files.append(d)
    # list datarecorder path.
    lst = os.listdir(extraPath)
    for d in lst:
        if d.endswith(".dat") or d.endswith(".log") or d.endswith(".bin"):
            extrafiles.append(d)
    # list files found on usb drive if any.
    try:
        if rpi_hardware.mount_usb_drive() == True:
            usbpath = "/mnt/usb/"
            lst = os.listdir(usbpath)
            for d in lst:
                if d.endswith(".dat") or d.endswith(".log") or d.endswith(".bin"):
                    usbfiles.append(d)
        else:
            if(showErrorIfNoUSB==True): print("Not USB drive found.")
    except Exception as e: 
        if(showErrorIfNoUSB==True): 
            print(e)
            print("Error: finding USB drive.")
        pass

    return files, extrafiles, usbfiles

##############################################
## function: listLogDataFiles()
def listLogDataFiles():
    from lib.common import shared 

    files,extrafiles,usbfiles = getLogDataFiles()
    extraPath = readConfig("DataRecorder", "path", shared.DefaultFlightLogDir)
    print("\nYour Log output files: (located in "+extraPath+")")
    for file in extrafiles:
        print(file)
    return 

##############################################
## function: listExampleLogs()
def listExampleLogs():
    files,extrafiles,usbfiles = getLogDataFiles()
    print("\nAvailable log demo files: (located in lib/inputs/_example_data folder)")
    for file in files:
        print(file)
    return 

##############################################
## function: listUSBLogDataFiles()
def listUSBLogDataFiles():
    files,extrafiles,usbfiles = getLogDataFiles(showErrorIfNoUSB=True)
    if(len(usbfiles)>0):
        print("\nUSB Log files found:")
        for file in usbfiles:
            print(file)
    return 

##############################################
## function: getDataRecorderDir()
## creates the data dir if it doesn't already exist..
## return fullpath if succes or already exists.
def getDataRecorderDir(exitOnFail=False):
    from os.path import exists
    import os
    from pathlib import Path
    from lib.common import shared 

    path_datarecorder = readConfig("DataRecorder", "path", shared.DefaultFlightLogDir)
    fullpath = ""
    try:
        user_home = str(Path.home())
        fullpath = path_datarecorder.replace("~",user_home) # expand out full user dir if it's in the path.
        if(exists(fullpath)==False):
            print("Creating DataRecorder dir: "+fullpath)
            os.mkdir(fullpath) # make sure the dir exists..
    except Exception as e: 
        print(e)
        print("Error DataRecorder dir: "+fullpath)
        shared.Dataship.errorFoundNeedToExit = True
        if(exitOnFail==True): sys.exit()
        return False
    if fullpath.endswith('/')==False: fullpath = fullpath + "/" # add a slash if needed.
    return fullpath

##############################################
## function: setupDirs()
## setup the directories for the system.
def setupDirs():
    # find data dir
    path_data = readConfig("Main", "data_dir", "./data/")
    # if it doesn't end with / then add it.
    if not path_data.endswith('/'):
        path_data = path_data + '/'
    if not os.path.exists(path_data):
        os.makedirs(path_data)
    # check for screens subdir
    path_screens = path_data + "screens/"
    if not os.path.exists(path_screens):
        os.makedirs(path_screens)
        


##############################################
## function: findInput()
## list python input source classes available to show in the lib/inputs dir.
def findInput(name=""):
    lst = os.listdir("lib/inputs")
    if name == "":
        print("\nAvailable input source modules: (located in lib/inputs folder)")
    for d in lst:
        if d.endswith(".py") and not d.startswith("_"):
            inputName = d[:-3]
            if name == "": # if no name passed in then print out all input sources.
                print(inputName, end=", ")
            else:
                if inputName == name: # found input
                    return True
    if name != "":
        return False
    else:
        print("") # print on new line.


# vi: modeline tabstop=8 expandtab shiftwidth=4 softtabstop=4 syntax=python

