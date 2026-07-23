#!/bin/bash
# Run TronView with a menu for selecting demos and options
# using dialog to build menus.  https://man.uex.se/1/dialog
# Nov 22, 2024.  Topher.

# Get absolute paths
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
TRONVIEW_DIR="$(dirname "$SCRIPT_DIR")"

if [[ "$OSTYPE" == "darwin"* ]]; then # Check if we're running on macOS
    RUN_PREFIX=""
else # else Linux we have to do everything as sudo so the app gets access to the serial ports and i2c
    RUN_PREFIX="sudo"
fi

# get version (updated to use TRONVIEW_DIR)
VERSION=$(PYTHONPATH=$TRONVIEW_DIR python3 -c "from lib.version import __version__; print(__version__)")
BUILD=$(PYTHONPATH=$TRONVIEW_DIR python3 -c "from lib.version import __build__; print(__build__)")
BUILD_DATE=$(PYTHONPATH=$TRONVIEW_DIR python3 -c "from lib.version import __build_date__; print(__build_date__)")
BUILD_TIME=$(PYTHONPATH=$TRONVIEW_DIR python3 -c "from lib.version import __build_time__; print(__build_time__)")

RUN_MENU_AGAIN=true

# Create data directory if it doesn't exist
$RUN_PREFIX mkdir -p "$TRONVIEW_DIR/data"
$RUN_PREFIX mkdir -p "$TRONVIEW_DIR/data/system"

# refresh available serial ports output file.
$RUN_PREFIX python3 $TRONVIEW_DIR/util/menu/serial_getlist.py -o data/system/available_serial_ports.json

# Check if ccze is installed (for colorizing console logs)
if ! command -v ccze &> /dev/null; then
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "ccze is not installed. Installing..."
        sudo apt-get install ccze -y
    fi
fi

# Function to save last run configuration
save_last_run() {
    local name="$1"
    local args="$2"
    local add_args="$3"
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    local auto_run="$4"    
    
    # Create the JSON content first
    local json_content='{
    "name": "'"$name"'",
    "args": "'"$args"'",
    "add_args": "'"$add_args"'",
    "timestamp": "'"$timestamp"'",
    "auto_run": '"$auto_run"'
}'
    
    # Use tee with sudo to write the file
    echo "$json_content" | $RUN_PREFIX tee "$TRONVIEW_DIR/data/system/last_run.json" >/dev/null
    
    # check for success
    if [ $? -ne 0 ]; then
        echo "Error saving ($RUN_PREFIX) last run configuration to $TRONVIEW_DIR/data/system/last_run.json"
    fi
}

# Function to run python commands
run_python() {
    local choice="$1"
    local ADD_ARGS="$2"

    cd "$TRONVIEW_DIR" || exit
    echo "Running from directory: $(pwd)"
    echo "Using Python: $(which python3)"

    # if $ADD_ARGS contains --console-log-debug, then remove it and replace with the following:
    # of if $* contains --console-log-debug, then remove it and replace with the following:
    # or if $LAST_ADD_ARGS contains --console-log-debug, then remove it and replace with the following:
    if [[ "$ADD_ARGS" == *"--console-log-debug"* || "$LAST_ADD_ARGS" == *"--console-log-debug"* ]]; then
        echo "Opening console log file: data/console_logs/last-console.log"
        # remove --console-log-debug from the command line arguments
        ADD_ARGS=$(echo "$ADD_ARGS" | sed 's/--console-log-debug//g')
        today=$(date +%Y-%m-%d_%H:%M:%S)
        log_file="data/console_logs/last-console.log"
        $RUN_PREFIX mkdir -p data/console_logs
        $RUN_PREFIX rm -f $log_file
        echo "log_file: $log_file run_prefix: $RUN_PREFIX"
        # clear the file and put today's date on the first line. then line feed.
        echo "##Date Run: $today" | $RUN_PREFIX tee $log_file > /dev/null
        # get __build_version__ from lib/version.py
        BUILD_VERSION=$(PYTHONPATH=$TRONVIEW_DIR python3 -c "from lib.version import __build_version__; print(__build_version__)")
        echo "##Build Version: $BUILD_VERSION" | $RUN_PREFIX tee -a $log_file > /dev/null
        echo "" | $RUN_PREFIX tee -a $log_file > /dev/null
        
        # Setup Python to run with unbuffered output
        # The -u flag to Python forces unbuffered output
        echo "Running with unbuffered output to console and log file..."
        
        if command -v stdbuf &> /dev/null; then
            # Use stdbuf to force unbuffered standard output and error
            $RUN_PREFIX stdbuf -o0 -e0 python3 -u $TRONVIEW_DIR/main.py $choice $ADD_ARGS 2>&1 | $RUN_PREFIX tee -a $log_file
        else
            # If stdbuf isn't available, just use Python's unbuffered mode (-u flag)
            # Setting PYTHONUNBUFFERED ensures all Python output is unbuffered
            PYTHONUNBUFFERED=1 $RUN_PREFIX python3 -u $TRONVIEW_DIR/main.py $choice $ADD_ARGS 2>&1 | $RUN_PREFIX tee -a $log_file
        fi
        
        return $?
    fi

    # run the python app with any additional arguments
    eval "$RUN_PREFIX python3 $TRONVIEW_DIR/main.py $choice $ADD_ARGS"
}

# Check if dialog is installed
if ! command -v dialog &> /dev/null; then
    echo "dialog is not installed. Installing..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew install dialog
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        sudo apt-get install dialog -y
    else
        echo "Please install dialog manually"
        exit 1
    fi
fi

# Check if we're running on macOS.  Create a python virtual environment and activate it.
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "Activating venv at: $TRONVIEW_DIR/venv/bin/activate"
    source "$TRONVIEW_DIR/venv/bin/activate"
    which python3
fi

# kill any running python3 processes
#$RUN_PREFIX pkill -f 'python3'

# Function to load last run configuration
load_last_run() {
    LAST_RUN_FILE="$TRONVIEW_DIR/data/system/last_run.json"
    if [ -f "$LAST_RUN_FILE" ]; then
        # if jq in not installed then install it on linux
        if ! command -v jq &> /dev/null; then
            if [[ "$OSTYPE" == "linux-gnu"* ]]; then
                echo "jq is not installed. Installing..."
                sudo apt-get install jq -y
            fi
            if [[ "$OSTYPE" == "darwin"* ]]; then
                brew install jq
            fi
        fi

        # Load last run configuration
        if command -v jq &> /dev/null; then
            LAST_NAME=$(jq -r '.name' "$LAST_RUN_FILE")
            LAST_ARGS=$(jq -r '.args' "$LAST_RUN_FILE")
            LAST_ADD_ARGS=$(jq -r '.add_args' "$LAST_RUN_FILE")
            LAST_TIME=$(jq -r '.timestamp' "$LAST_RUN_FILE")
            LAST_AUTO_RUN=$(jq -r '.auto_run' "$LAST_RUN_FILE")
        fi
    fi
}

# Function to handle menu exit codes
handle_menu_exit() {
    local exit_status=$1
    if [ $exit_status -ne 0 ]; then  # Changed from -eq 1 to -ne 0
        if [ "$2" = "main" ]; then
            #clear
            echo "Exiting..."
            exit 0
        else
            return 1  # Return to previous menu
        fi
    fi
    return 0
}

# Get a single character input without waiting for return
get_char() {
    # Save current terminal settings
    old_tty=$(stty -g)
    # Set terminal to raw mode
    stty raw -echo
    # Read single character
    char=$(dd if=/dev/tty bs=1 count=1 2>/dev/null)
    # Restore terminal settings
    stty "$old_tty"
    # Output the character
    echo "$char"
}

################################################################################
################################################################################
## AUTO-RUN ???
# If there was a last run, show dialog to run it again
load_last_run
# check if --skiplastrun is in the command line arguments
if [[ ! " $* " =~ "--skiplastrun" ]]; then
    if [ -f "$LAST_RUN_FILE" ] && [ "$LAST_AUTO_RUN" = "true" ]; then
        exec 3>&1
        dialog --clear \
               --title "TronView Auto-Run in 10 seconds" \
               --pause "\nRun TronView: $LAST_NAME\n\nPress OK to run again\nPress Cancel or ESC for menu" \
               12 60 10
        exit_status=$?
        exec 3>&-
        #echo "Last run exit status: $exit_status"
        case $exit_status in
            0)  # OK pressed or timeout
                choice="$LAST_ARGS"
                ADD_ARGS="$LAST_ADD_ARGS"
                selected_name="$LAST_NAME"
                SHOW_ADDITIONAL_OPTIONS=false
                # Run the command immediately
                if [ ! -z "$choice" ]; then
                    run_python "$choice" "$LAST_ADD_ARGS"
                fi
                exit 0
                ;;
            255)  # ESC pressed
                ;;
            1|*)    # Cancel/ESC pressed or any other result
                # Continue to main menu
                ;;
            esac
    fi
fi


################################################################################
################################################################################
## MAIN MENU
# Show 1st level main menu
# Create menu options array
    declare -a menu_options=(
        "Live Setup" "Live input setup options"
        "MGL Demos" "MGL related demos and tests" 
        "Dynon Demos" "Dynon related demos"
        "Stratux Demos" "Stratux only demos"
        "IMU Options" "IMU related options and tests"
        "Utils" "Utils & Tests, Serial, Joystick, I2c, WIFI"
        "Update" "Update TronView & View Changelog"
    )


ASCII_ART='
_____             __     ___               \n
|_   _| __ ___  _ _\ \   / (_) _____      __\n
  | || '"'"'__/ _ \| '"'"'_ \ \ / /| |/ _ \ \ /\ / /\n
  | || | | (_) | | | \ V / | |  __/\ V  V / \n
  |_||_|  \___/|_| |_|\_/  |_|\___| \_/\_/  \n
'

# Check if glow is installed.  This is used to render markdown files in the terminal
if ! command -v glow &> /dev/null; then
    echo "glow is not installed. Installing..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew install glow
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        sudo mkdir -p /etc/apt/keyrings
        curl -fsSL https://repo.charm.sh/apt/gpg.key | sudo gpg --dearmor -o /etc/apt/keyrings/charm.gpg
        echo "deb [signed-by=/etc/apt/keyrings/charm.gpg] https://repo.charm.sh/apt/ * *" | sudo tee /etc/apt/sources.list.d/charm.list
        sudo apt update && sudo apt install glow
    fi
fi

while $RUN_MENU_AGAIN; do

    # make sure the last run is updated.  They could have just ran something and updated the json file
    load_last_run
    if [ -f "$LAST_RUN_FILE" ]; then
        menu_options_with_last_run=("Last Run" "$LAST_NAME" "${menu_options[@]}")
    else
        # else just use the normal menu options
        menu_options_with_last_run=("${menu_options[@]}")
    fi

    ################################################################################
    ################################################################################
    ## MAIN MENU
    # Show 1st level main menu
    while true; do
        exec 3>&1
        DIALOG_TIMEOUT=0
        choice=$(dialog --clear \
                        --title "Startup script" \
                        --menu "$ASCII_ART\nVersion: $VERSION Build: $BUILD $BUILD_DATE $BUILD_TIME" 22 70 10 \
                        "${menu_options_with_last_run[@]}" \
                        2>&1 1>&3)
        exit_status=$?
        exec 3>&-
        
        handle_menu_exit $exit_status "main" || exit 0

        # Handle main menu selection
        case $choice in
            ############################################################################
            "Live Setup")
                SHOW_ADDITIONAL_OPTIONS=true
                choice=""
                InputNum=0
                while [ $InputNum -lt 1 ]; do
                    exec 3>&1
                    options=$(dialog --clear --title "Input Options" \
                                --checklist "Use space bar to select 1 or more Inputs :" 20 60 10 \
                                "serial_mgl" "MGL Serial" OFF \
                                "serial_d100" "Dynon D100 Serial" OFF \
                                "serial_skyview" "Dynon Skyview Serial" OFF \
                                "serial_g3x" "Garmin G3x Serial" OFF \
                                "serial_onspeedaoa" "OnSpeed AOA Serial" OFF \
                                "serial_grt_eis" "Grand Rapids EIS Serial" OFF \
                                "serial_nmea" "NMEA Serial" OFF \
                                "gyro_i2c_bno055" "BNO055 IMU i2c (Pi only)" OFF \
                                "gyro_i2c_bno055" "2nd BNO055 IMU i2c (Pi only)" OFF \
                                "gyro_i2c_bno085" "BNO085 IMU i2c (Pi only)" OFF \
                                "gyro_i2c_bno085" "2nd BNO085 IMU i2c (Pi only)" OFF \
                                "stratux_wifi" "Stratux WIFI Compatible Device" OFF \
                                "levil_wifi" "iLevil B.O.M WiFi (UDP)" OFF \
                                "meshtastic" "Meshtastic Serial" OFF \
                                "gyro_virtual" "Virtual IMU" OFF \
                                "gyro_virtual" "2nd Virtual IMU" OFF \
                                "gyro_joystick" "Joystick vIMU" OFF \
                                "adc_ads1115" "Analog Input ADS1115 (Pi only)" OFF \
                                2>&1 1>&3)
                    exit_status=$?
                    exec 3>&-

                    if handle_menu_exit $exit_status "sub"; then
                        # check if user selected any options
                        if [ -z "$options" ]; then
                            dialog --clear --title "Error" --msgbox "No inputs selected.  TronView needs at least one input selected." 10 60
                            choice=""                        
                        fi

                        InputNum=0
                        # Convert options to array using more compatible syntax
                        selected_opts=( $(echo "$options" | sed 's/"//g') )
                        
                        for opt in "${selected_opts[@]}"; do
                            # Skip if empty
                            [ -z "$opt" ] && continue
                            InputNum=$((InputNum+1))
                            choice="$choice --in$InputNum $opt"
                            selected_name="$selected_name $opt"
                        done
                        break
                    else
                        choice=""
                        break
                    fi

                done
                ;;

            ############################################################################
            "MGL Demos")
                SHOW_ADDITIONAL_OPTIONS=true
                while true; do
                    exec 3>&1
                    subchoice=$(dialog --clear --title "MGL Demos" \
                                      --menu "Choose a demo:" 20 60 10 \
                                      "1" "MGL + Stratux + vIMU - chasing traffic" \
                                      "2" "MGL - G430 CDI" \
                                      "3" "MGL - Gyro Test" \
                                      "4" "MGL + Stratux RV6 Chase 1" \
                                      "5" "MGL + Stratux RV6 Chase 2" \
                                      "6" "MGL + Stratux RV6 Chase 3" \
                                      2>&1 1>&3)
                    exit_status=$?
                    exec 3>&-
                    
                    if handle_menu_exit $exit_status "sub"; then
                        selected_name=""
                        case $subchoice in
                            1) 
                                choice="--in1 serial_mgl --playfile1 mgl_8.dat --in2 stratux_wifi --playfile2 stratux_8.dat --in3 gyro_virtual"
                                selected_name="MGL + Stratux + vIMU - chasing traffic"
                                ;;
                            2) 
                                choice="--in1 serial_mgl -c MGL_G430_Data_3Feb19_v7_Horz_Vert_Nedl_come_to_center.bin"
                                selected_name="MGL - G430 CDI"
                                ;;
                            3) 
                                choice="--in1 serial_mgl -c mgl_data1.bin"
                                selected_name="MGL - Gyro Test"
                                ;;
                            4) 
                                choice="--in1 serial_mgl --playfile1 mgl_chase_rv6_1.dat --in2 stratux_wifi --playfile2 stratux_chase_rv6_1.dat --in3 gyro_virtual"
                                selected_name="MGL + Stratux RV6 Chase 1"
                                ;;
                            5) 
                                choice="--in1 serial_mgl --playfile1 mgl_chase_rv6_2.dat --in2 stratux_wifi --playfile2 stratux_chase_rv6_2.dat --in3 gyro_virtual"
                                selected_name="MGL + Stratux RV6 Chase 2"
                                ;;
                            6) 
                                choice="--in1 serial_mgl --playfile1 mgl_chase_rv6_3.dat --in2 stratux_wifi --playfile2 stratux_chase_rv6_3.dat --in3 gyro_virtual"
                                selected_name="MGL + Stratux RV6 Chase 3"
                                ;;
                        esac
                        break
                    else
                        choice=""
                        break
                    fi
                done
                ;;
            ############################################################################
            "Dynon Demos")
                SHOW_ADDITIONAL_OPTIONS=true
                while true; do
                    exec 3>&1
                    subchoice=$(dialog --clear --title "Dynon Demos" \
                                      --menu "Choose a demo:" 20 60 10 \
                                      "1" "Dynon D100" \
                                      "2" "Dynon Skyview" \
                                      2>&1 1>&3)
                    exit_status=$?
                    exec 3>&-
                    
                    if handle_menu_exit $exit_status "sub"; then
                        case $subchoice in
                            1) 
                                choice="--in1 serial_d100 -e"
                                selected_name="Dynon D100"
                                ;;
                            2) 
                                choice="--in1 serial_skyview -e"
                                selected_name="Dynon Skyview"
                                ;;
                        esac
                        break  # Break just the inner loop
                    else
                        choice=""  # Clear the choice
                        break  # Break the inner loop to return to main menu
                    fi
                done
                ;;
            ############################################################################
            "Stratux Demos")
                SHOW_ADDITIONAL_OPTIONS=true
                while true; do
                    exec 3>&1
                    subchoice=$(dialog --clear --title "Stratux Demos" \
                                      --menu "Choose a demo:" 20 60 10 \
                                      "1" "Live Stratux Connection" \
                                      "2" "Demo Data 54" \
                                      "3" "Demo Data 57 (Bad pitch/roll)" \
                                      "4" "Demo Data stratux_8 - Traffic targets only" \
                                      2>&1 1>&3)
                    exit_status=$?
                    exec 3>&-
                    
                    if handle_menu_exit $exit_status "sub"; then
                        case $subchoice in
                            1) choice="--in1 stratux_wifi"
                                selected_name="Live Stratux Connection"
                                ;;
                            2) 
                                choice="--in1 stratux_wifi -c stratux_54.dat"
                                selected_name="Demo 54"
                                ;;
                            3) 
                                choice="--in1 stratux_wifi -c stratux_57.dat"
                                selected_name="Demo 57 (Bad pitch/roll)"
                                ;;
                            4) 
                                choice="--in1 stratux_wifi -c stratux_8.dat"
                                selected_name="Demo stratux_8 - Traffic targets only"
                                ;;
                        esac
                        break  # Break just the inner loop
                    else
                        choice=""  # Clear the choice
                        break  # Break the inner loop to return to main menu
                    fi
                done
                ;;
            ############################################################################
            "IMU Options")
                SHOW_ADDITIONAL_OPTIONS=true
                while true; do
                    exec 3>&1
                    subchoice=$(dialog --clear --title "IMU Options & Tests" \
                                      --menu "Choose a IMU Option:" 20 60 10 \
                                      "1" "BNO085 calibration (Pi only)" \
                                      "2" "Live BNO055 IMU (Pi only)" \
                                      "3" "Live BNO055 IMU & MGL (Pi only)" \
                                      "4" "Live BNO055 IMU + MGL + Stratux (Pi only)" \
                                      "5" "Live dual BNO055 IMUs (Pi only)" \
                                      "6" "Live BNO085 IMU (Pi only)" \
                                      "7" "Live dual BNO085 IMUs + Live Stratux (Pi only)" \
                                      "8" "MGL + Stratux + Live BNO085" \
                                      "9" "vIMU + Live BNO085 (Pi only)" \
                                      "10" "joystick vIMU + Live BNO085 (Pi only)" \
                                      "11" "1 Virtual IMU" \
                                      "12" "2 Virtual IMUs" \
                                      "13" "Joystick vIMU + Virtual IMU" \
                                      2>&1 1>&3)
                    exit_status=$?
                    exec 3>&-
                    
                    if handle_menu_exit $exit_status "sub"; then
                        case $subchoice in
                            1) FULL_COMMAND="$RUN_PREFIX python3 $TRONVIEW_DIR/util/rpi/i2c/calibrate_bno085.py" 
                               choice=""
                               break 2 
                               ;;
                            2) choice="--in1 gyro_i2c_bno055"
                                selected_name="Live BNO055"
                                ;;
                            3) choice="--in1 gyro_i2c_bno055 --in1 serial_mgl --playfile1 mgl_data1.bin"
                                selected_name="Live BNO055 & MGL"
                                ;;
                            4) choice="--in1 serial_mgl --playfile1 mgl_chase_rv6_1.dat --in2 stratux_wifi --playfile2 stratux_chase_rv6_1.dat --in3 gyro_i2c_bno055"
                                selected_name="Live BNO055 + MGL + Stratux"
                                ;;
                            5) choice="--in1 gyro_i2c_bno055 --in2 gyro_i2c_bno055"
                                selected_name="Live dual BNO055"
                                ;;
                            6) choice="--in1 gyro_i2c_bno085"
                                selected_name="Live BNO085"
                                ;;
                            7) choice="--in1 gyro_i2c_bno085 --in2 gyro_i2c_bno085 --in3 stratux_wifi"
                                selected_name="Live dual BNO085"
                                ;;
                            8) choice="--in1 serial_mgl --playfile1 mgl_chase_rv6_1.dat --in3 stratux_wifi --playfile3 stratux_chase_rv6_1.dat --in2 gyro_i2c_bno085"
                                selected_name="MGL + Stratux + Live BNO085"
                                ;;
                            9) choice="--in1 gyro_virtual --in2 gyro_i2c_bno085"
                                selected_name="vIMU + Live BNO085"
                                ;;
                            10) choice="--in1 gyro_joystick --in2 gyro_i2c_bno085"
                                selected_name="joystick vIMU + Live BNO085"
                                ;;
                            11) choice="--in1 gyro_virtual"
                                selected_name="1 Virtual IMU"
                                ;;
                            12) choice="--in1 gyro_virtual --in2 gyro_virtual"
                                selected_name="2 Virtual IMUs"
                                ;;
                            13) choice="--in1 gyro_joystick --in2 gyro_virtual"
                                selected_name="Joystick vIMU + Virtual IMU"
                                ;;
                        esac
                        break  # Break just the inner loop
                    else
                        choice=""  # Clear the choice
                        break  # Break the inner loop to return to main menu
                    fi
                done
                ;;
            ############################################################################
            "Utils")
                SHOW_ADDITIONAL_OPTIONS=false
                choice=""
                while true; do
                    exec 3>&1
                    subchoice=$(dialog --clear --title "Utility Options" \
                                      --menu "Choose a option:" 20 60 10 \
                                      "1" "List Serial Ports" \
                                      "2" "Edit TronView Config File (config.cfg)" \
                                      "3" "Download FAA Aircraft Database" \
                                      "4" "View last console log" \
                                      "5" "Test Joystick" \
                                      "6" "Raw Serial Read" \
                                      "7" "Read Serial MGL" \
                                      "8" "Read Serial Dynon Skyview" \
                                      "9" "Read Serial Garmin G3x" \
                                      "10" "Read NMEA GPS data" \
                                      "11" "Test Stratux and iLevil WiFi connection" \
                                      "12" "I2C Test (Pi only)" \
                                      2>&1 1>&3)
                    exit_status=$?
                    exec 3>&-
                    
                    if handle_menu_exit $exit_status "sub"; then
                        case $subchoice in
                            1) FULL_COMMAND="$RUN_PREFIX python3 $TRONVIEW_DIR/util/menu/serial_getlist.py --select" 
                                SKIP_PAUSE=false;;
                            2) FULL_COMMAND="pico $TRONVIEW_DIR/config.cfg"
                               # check if $TRONVIEW_DIR/config.cfg exists.. if not
                               if [ ! -f "$TRONVIEW_DIR/config.cfg" ]; then
                                    cp $TRONVIEW_DIR/config_example.cfg $TRONVIEW_DIR/config.cfg
                               fi
                               ;;
                            3) FULL_COMMAND="$RUN_PREFIX python3 $TRONVIEW_DIR/util/menu/faa_register.py --download-only"
                               SKIP_PAUSE=false
                               ;;
                            4) 
                               # check if ccze is installed.. if not use just less
                               if command -v ccze &> /dev/null; then
                                    FULL_COMMAND="$RUN_PREFIX cat $TRONVIEW_DIR/data/console_logs/last-console.log | ccze -A | less -R"
                               else
                                    FULL_COMMAND="$RUN_PREFIX less $TRONVIEW_DIR/data/console_logs/last-console.log"
                               fi
                               ;;
                            5) FULL_COMMAND="$RUN_PREFIX python3 $TRONVIEW_DIR/util/tests/joystick.py" ;;
                            6) FULL_COMMAND="$RUN_PREFIX python3 $TRONVIEW_DIR/util/tests/serial_raw.py" ;;
                            7) FULL_COMMAND="$RUN_PREFIX python3 $TRONVIEW_DIR/util/tests/serial_read.py -m" ;;
                            8) FULL_COMMAND="$RUN_PREFIX python3 $TRONVIEW_DIR/util/tests/serial_read.py -s" ;;
                            9) FULL_COMMAND="$RUN_PREFIX python3 $TRONVIEW_DIR/util/tests/serial_read.py -g" ;;
                            10) FULL_COMMAND="$RUN_PREFIX python3 $TRONVIEW_DIR/util/tests/nmea_gps.py -a" ;;
                            11) FULL_COMMAND="$RUN_PREFIX $TRONVIEW_DIR/util/tests/test_stratux_wifi.sh" ;;
                            12) FULL_COMMAND="$RUN_PREFIX python3 $TRONVIEW_DIR/util/tests/i2c_test.py" ;;
                        esac
                        echo "Running: $FULL_COMMAND"
                        #exit 0
                        # goto the end of the loop
                        break 2
                    else

                        break  # Break the inner loop to return to main menu
                    fi
                done
                ;;
            ############################################################################
            "Update")
                SHOW_ADDITIONAL_OPTIONS=false
                choice=""
                # get current branch
                current_branch=$(git -C "$TRONVIEW_DIR" rev-parse --abbrev-ref HEAD)
                # get latest branch by date
                git -C "$TRONVIEW_DIR" fetch --all
                # remove HEAD -> from branch name (with extra spaces) if it exists 
                # and remove /origin/ from the beginning of the branch name
                latest_branch=$(git -C "$TRONVIEW_DIR" branch -r --sort=-committerdate | head -n 1 | sed 's/^.*origin\///' | sed 's/^HEAD -> //')
                # get date of latest branch
                latest_branch_date=$(git -C "$TRONVIEW_DIR" show -s --format=%ci $latest_branch)

                # get 3 latest branches
                latest_branch2nd=$(git -C "$TRONVIEW_DIR" branch -r --sort=-committerdate | head -n 2 | tail -n 1 | sed 's/^.*origin\///' | sed 's/^HEAD -> //')
                latest_branch2nd_date=$(git -C "$TRONVIEW_DIR" show -s --format=%ci $latest_branch2nd)

                latest_branch3rd=$(git -C "$TRONVIEW_DIR" branch -r --sort=-committerdate | head -n 3 | tail -n 1 | sed 's/^.*origin\///' | sed 's/^HEAD -> //')
                latest_branch3rd_date=$(git -C "$TRONVIEW_DIR" show -s --format=%ci $latest_branch3rd)

                # get 4th latest branch
                latest_branch4th=$(git -C "$TRONVIEW_DIR" branch -r --sort=-committerdate | head -n 4 | tail -n 1 | sed 's/^.*origin\///' | sed 's/^HEAD -> //')
                latest_branch4th_date=$(git -C "$TRONVIEW_DIR" show -s --format=%ci $latest_branch4th)

                while true; do
                    exec 3>&1
                    subchoice=$(dialog --clear --title "Update (via github)" \
                                      --menu "Choose:" 20 60 10 \
                                      "1" "Update TronView (current branch: $current_branch)" \
                                      "2" "View CHANGELOG.md" \
                                      "3" "Branch: $latest_branch ($latest_branch_date)" \
                                      "4" "Branch: $latest_branch2nd ($latest_branch2nd_date)" \
                                      "5" "Branch: $latest_branch3rd ($latest_branch3rd_date)" \
                                      "6" "Branch: $latest_branch4th ($latest_branch4th_date)" \
                                      2>&1 1>&3)
                    exit_status=$?
                    exec 3>&-

                    if handle_menu_exit $exit_status "sub"; then
                        RUN_AGAIN=false
                        case $subchoice in
                            1) FULL_COMMAND="git -C $TRONVIEW_DIR pull" 
                                RUN_AGAIN=true
                                ;;
                            2) 
                                if command -v glow &> /dev/null; then
                                    FULL_COMMAND="glow $TRONVIEW_DIR/CHANGELOG.md"
                                else
                                    FULL_COMMAND="less $TRONVIEW_DIR/CHANGELOG.md"
                                fi
                                break 2
                                ;;
                            3) FULL_COMMAND="git -C $TRONVIEW_DIR checkout $latest_branch && git -C $TRONVIEW_DIR pull" 
                                RUN_AGAIN=true
                                ;;
                            4) FULL_COMMAND="git -C $TRONVIEW_DIR checkout $latest_branch2nd && git -C $TRONVIEW_DIR pull" 
                                RUN_AGAIN=true
                                ;;
                            5) FULL_COMMAND="git -C $TRONVIEW_DIR checkout $latest_branch3rd && git -C $TRONVIEW_DIR pull" 
                                RUN_AGAIN=true
                                ;;
                            6) FULL_COMMAND="git -C $TRONVIEW_DIR checkout $latest_branch4th && git -C $TRONVIEW_DIR pull" 
                                RUN_AGAIN=true
                                ;;
                        esac
                        break 2
                    else
                        break
                    fi
                done
                ;;
            ############################################################################
            "Last Run")
                choice="$LAST_ARGS"
                SHOW_ADDITIONAL_OPTIONS=false
                break
                ;;
        esac

        ############################################################################
        # Additional Options Menu
        # If we have a valid choice, show additional options
        if [ ! -z "$choice"  ] && $SHOW_ADDITIONAL_OPTIONS; then
            # Clear the dialog window
            #clear

            # Additional options dialog
            exec 3>&1
            options=$(dialog --clear --title "Additional Options" \
                            --checklist "Use space bar to select 1 or more options :" 20 60 10 \
                            "multi" "Run multiple threads (beta feature)" OFF \
                            "debug" "save output (saves to data/console_logs/last-console.log)" ON \
                            "auto" "Auto-run next time" OFF \
                            2>&1 1>&3)
            exit_status=$?
            exec 3>&-

            # If escape was pressed, go back to main menu
            if ! handle_menu_exit $exit_status "sub"; then
                choice=""
                continue  # Continue the main menu loop
            fi

            # Process additional options
            ADD_ARGS=""
            [[ $options == *"multi"* ]] && ADD_ARGS="$ADD_ARGS --input-threads"

            if [[ $options == *"debug"* ]]; then
                ADD_ARGS=" --console-log-debug"
            fi  

            if [[ $options == *"auto"* ]]; then
                # make sure we are on linux
                selected_auto_run="true"
            else
                selected_auto_run="false"
            fi

            # Before running the command, save the configuration
            if [ ! -z "$choice" ] && [ "$choice" != "$LAST_ARGS" ]; then
                save_last_run "$selected_name" "$choice" "$ADD_ARGS" "$selected_auto_run"
            fi

            # Break the main loop to run the command
            break
        fi
    done

    # Only run if we have a valid choice
    if [ ! -z "$choice" ]; then
        # Clear the dialog window
        #clear
        # Run the selected command
        if [[ "$OSTYPE" == "linux-gnu"* ]] || [[ ! "$choice" =~ "bno" ]]; then
            run_python "$choice" "$ADD_ARGS"
            exit_status=$?
            if [ $exit_status -ne 0 ]; then
                echo "[Error detected. Press any key to continue...]"
                get_char
            else
                echo "[Press any key to go back to the TronView menu]"
                get_char
            fi
            # clear $choice
            choice=""
        else
            echo "IMU options only supported on Linux/Raspberry Pi"
            echo "[Press any key to continue...]"
            get_char
        fi
    fi

    # Run the full command if it was set. example: python3 $TRONVIEW_DIR/util/tests/joystick.py
    if [ ! -z "$FULL_COMMAND" ]; then
        eval "$FULL_COMMAND"
        if [ "$SKIP_PAUSE" != "true" ]; then
            echo "[Press any key to go back to the TronView menu]"
            get_char
        fi
        # clear $FULL_COMMAND
        FULL_COMMAND=""
        SKIP_PAUSE=""
        if $RUN_AGAIN; then  # if we need to run again, skip the last run
            exec "$0" "--skiplastrun"
            exit 0
        fi
    fi

done

echo "To run again type: ./util/run.sh (make sure you are in the TronView directory)"

