# Demo Sample EFIS Data

  Demo data is saved in lib/inputs/_example_data .  Demo data lets you run previously recorded data through the hud app for demo or testing purposes.  Each input source module uses it's own format for data.  So for example if you want to run dynon demo data then you must run it through the dynon input source module.
  
  Using the -c FILENAME command line option loads data from the _example_data folder.
  
  Example to run the MGL_2.dat demo data file would look like this:
  
  `sudo python3 main.py --in1 serial_mgl --playfile1 MGL_2.dat`

  Note this is setting up input1.


# MGL Data

  MGL EFIS Sample Data Link: https://drive.google.com/open?id=1mPOmQuIT-Q5IvIoVmyfRCtvBxCsLUuvz

  MGL EFIS Serial Protocol Link: https://drive.google.com/open?id=1OYj000ghHJqSfvacaHMO-jOcfd1raoVo

  MGL example data in this git repo include: (they can be ran by using the -c <filename> command line option.)

  MGL_V2.bin = G430_Bit_Test_24Mar19
  
  MGL_V3.bin = G430_Data_3Feb19_VertNdlFullUp_HzNdl_SltRt_toCtr
  
  MGL_V4.bin = G430_Data_3Feb19_HSI_Nedl_2degsRt_Vert_SlightLow
  
  MGL_V5.bin = G430_Data_3Feb19_HSI_Nedl_2degsLft_Vert_2Degs_Dwn
  
  MGL_V6.bin = G430_Data_3Feb19_HSI_Nedl_2degsRt_Vert_2Degs_Up
  
  MGL_V7.bin = G430_Data_3Feb19_Horz_Vert_Nedl_come to center
  
  MGL_V8.bin = G430_Data_13Ap19_VertNdlFullDwn_HzNdl_FullLft
  
  MGL_V9.bin = 13Ap_AltBug_0_500_1k_1.5k_to_10k_5.1K_5.2k_5.9kv10_v10
  
  MGL_V10.bin = 13Ap_XC_Nav 
  
  MGL_V11.bin = iEfis_NavDataCapture_5Feb19
  
  MGL_V12.bin = NavData_13Ap_HdgBug_360_10_20_30_to_360_001_002_003_to_010_v9

# Dynon Data

  Dynon Skyview EFIS Sample Data Link: https://drive.google.com/open?id=1jQ0q4wkq31C7BRn7qzMSMClqPw1Opwnp

  Dynon Skyview EFIS Serial Protocol Link: https://drive.google.com/open?id=1isurAOIiTzki4nh59lg6IDsy1XcsJqoG
  
  Dynon D100 Series EFIS Sample Data Link: https://drive.google.com/open?id=1_os-xv0Cv0AGFVypLfSeg6ucGv5lwDVj
  
  Dynon D100 Series EFIS Serial Protocol Link: https://drive.google.com/open?id=1vUBMJZC3W85fBu33ObuurYx81kj09rqE

# Garmin Data

  Garmin G3X EFIS Sample Data Link: https://drive.google.com/open?id=1gHPC3OipAs9K06wj5zMw_uXn3_iqZriS

  Garmin G3X EFIS Serial Protocol Link: https://drive.google.com/open?id=1uRRO-wdG7ya6_6-CfDVrZaKJsiYit-lm

# OnSpeed Data

  OnSpeed Gen3 emits its native display-serial stream (86-byte `#4` frames at 40 Hz, 115200 8N1) from the box's display UART — the same wire the OnSpeed M5Stack display consumes. It carries attitude, IAS, percent-lift AOA at tenths resolution, the aircraft's per-flap calibrated AOA band anchors (which drive the HUD AOA module's chevron/donut colors), flap position, VSI, OAT, G loads, G-onset rate, and deceleration rate.

  OnSpeed Display Serial Protocol reference: https://dev.flyonspeed.org/reference/serial-protocol/

  Requires OnSpeed firmware v4.25 or later with `SERIALOUTFORMAT=ONSPEED` (the default). The wire is versioned by its frame magic; older-firmware frames are dropped rather than mis-parsed.

  Live: `python3 main.py --in1 serial_onspeedaoa` (set the port in config.cfg under `[serial_onspeedaoa]`). The default screen's HUD AOA and Slip Skid modules pick the data up directly; the OnSpeed extras are bindable from the screen editor as `airData[N].OnSpeed_*` fields.

  Playback: any recording of the raw wire bytes plays back with `--in1 serial_onspeedaoa -e --playfile1 FILE.dat` — TronView's own data recorder writes one while flying, or capture the UART with any serial logger.

# Stratux Data

  Recorded data for stratux is saved in the example data.  stratux_1.dat shows traffic near by.  Like 0.5 miles away.
