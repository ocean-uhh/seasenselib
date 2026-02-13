MSM121_054_1db Dataset Report
=============================

*Generated: 2026-02-13 07:44:16 UTC*

Dataset Overview
^^^^^^^^^^^^^^^^

- **Source File**: examples/MSM121_054_1db.cnv
- **Original Format**: SeaBird CNV
- **Reader**: SbeCnvReader
- **Total Variables**: 23
- **Total Coordinates**: 3
- **Dataset Size**: 0.58 MB

- **Time Coverage**: 2000-01-01 to 2000-01-01
- **Record Length**: 3,593 observations
- **Sampling Frequency**: 0min

Dataset Visualization
^^^^^^^^^^^^^^^^^^^^

.. figure:: plots/MSM121_054_1db_profile.png
   :alt: Dataset CTD depth profile plot
   :align: center
   :scale: 80%

   Ctd Depth Profile plot showing temperature and salinity vs depth.
   Sampling frequency: 0.0 minutes.

Coordinate Information
^^^^^^^^^^^^^^^^^^^^^^

The following table shows information about dataset coordinates:

.. list-table::
   :widths: 16 16 16 16 16 16
   :header-rows: 1

   * - Coordinate
     - Description
     - Units
     - Shape
     - Min Value
     - Max Value
   * - **latitude**
     - Latitude
     - degrees_north
     - (3593,)
     - 49.70834
     - 49.71112
   * - **longitude**
     - Longitude
     - degrees_east
     - (3593,)
     - -45.00409
     - -45.00073
   * - **time**
     - Time
     - unknown
     - (3593,)
     - 2000-01-01T12:28:34
     - 2000-01-01T13:29:55


Variable Information
^^^^^^^^^^^^^^^^^^^^

The following table shows variable mappings from original to standardized names,
along with key statistics for each variable.

.. list-table::
   :widths: 15 15 15 15 15 15 15
   :header-rows: 1

   * - Variable
     - Description
     - Units
     - Shape
     - Min Value
     - Max Value
     - Missing %
   * - *t090C* → **temperature_1**
     - Temperature (SENSOR_TEMP_4456)
     - degC
     - (3593,)
     - 1.944
     - 14.286
     - 0.0%
   * - *t190C* → **temperature_2**
     - Temperature (SENSOR_TEMP_4156)
     - degC
     - (3593,)
     - 1.943
     - 14.286
     - 0.0%
   * - *c0mS/cm* → **conductivity_1**
     - Conductivity (SENSOR_CNDC_2646)
     - mS/cm
     - (3593,)
     - 32.109
     - 41.581
     - 0.0%
   * - *c1mS/cm* → **conductivity_2**
     - Conductivity (SENSOR_CNDC_2643)
     - mS/cm
     - (3593,)
     - 32.108
     - 41.580
     - 0.0%
   * - *prDM* → **pressure**
     - Pressure (SENSOR_PRES_0657)
     - db
     - (3593,)
     - 7.000
     - 3599.000
     - 0.0%
   * - *sbeox0ML/L* → **oxygen_1**
     - Oxygen
     - ml/l
     - (3593,)
     - 4.345
     - 6.970
     - 0.0%
   * - *sbeox1ML/L* → **oxygen_2**
     - Oxygen
     - ml/l
     - (3593,)
     - 4.226
     - 6.808
     - 0.0%
   * - **depth**
     - Depth
     - meters
     - (3593,)
     - -3538.187
     - -6.940
     - 0.0%
   * - **density**
     - Sea Water Density
     - kg m-3
     - (3593,)
     - 1025.326
     - 1044.021
     - 0.0%
   * - **potential_temperature_1**
     - Potential Temperature
     - degree_C
     - (3593,)
     - 1.655
     - 14.282
     - 0.0%
   * - **potential_temperature_2**
     - Potential Temperature
     - degree_C
     - (3593,)
     - 1.655
     - 14.281
     - 0.0%
   * - *sal11* → **salinity**
     - Salinity
     - 1
     - (3593,)
     - 33.994
     - 34.917
     - 0.0%
   * - **conservative_temperature_1**
     - Conservative Temperature
     - degC
     - (3593,)
     - 1.653
     - 14.286
     - 0.0%
   * - **conservative_temperature_2**
     - Conservative Temperature
     - degC
     - (3593,)
     - 1.652
     - 14.285
     - 0.0%
   * - **speed_of_sound**
     - Speed of Sound in Sea Water
     - m s-1
     - (3593,)
     - 1468.163
     - 1518.491
     - 0.0%
   * - **timeQ**
     - timeQ
     - seconds
     - (3593,)
     - 750083314.000
     - 750086995.000
     - 0.0%
   * - **timeS**
     - timeS
     - seconds
     - (3593,)
     - 134.461
     - 3815.453
     - 0.0%
   * - **flag**
     - flag
     - unknown
     - (3593,)
     - 0.000
     - 0.000
     - 0.0%


Sensor Variables
^^^^^^^^^^^^^^^^

The following table shows sensor metadata variables that contain
instrument information and calibration details.

.. list-table::
   :widths: 25 25 25 25
   :header-rows: 1

   * - Variable
     - Details
     - Vocabulary
     - Calibration Coefficients
   * - **SENSOR_CNDC_2643**
     - - long_name = Sea-Bird SBE 4C conductivity sensor sensor metadata
       - sensor_model = Sea-Bird SBE 4C conductivity sensor
       - sensor_maker = Sea-Bird Scientific
       - serial_number = 2643
       - calibration_date = 2022-10-27
       - channel = 5
     - - **Type**: http://vocab.nerc.ac.uk/collection/L05/current/133/
       - **Model**: https://vocab.nerc.ac.uk/collection/L22/current/TOOL0417/
       - **Maker**: http://vocab.nerc.ac.uk/collection/L35/current/MAN0013/
     - - **CONDUCTIVITY**: G=-9.90089056e+000, H=1.37876824e+000, I=-2.09415484e-003, J=2.10319217e-004, CPcor=-9.57000000e-008, CTcor=3.2500e-006, WBOTC=0.00000000e+000, Slope=1.00000000, Offset=0.00000
   * - **SENSOR_CNDC_2646**
     - - long_name = Sea-Bird SBE 4C conductivity sensor sensor metadata
       - sensor_model = Sea-Bird SBE 4C conductivity sensor
       - sensor_maker = Sea-Bird Scientific
       - serial_number = 2646
       - calibration_date = 2022-10-27
       - channel = 2
     - - **Type**: http://vocab.nerc.ac.uk/collection/L05/current/133/
       - **Model**: https://vocab.nerc.ac.uk/collection/L22/current/TOOL0417/
       - **Maker**: http://vocab.nerc.ac.uk/collection/L35/current/MAN0013/
     - - **CONDUCTIVITY**: G=-1.03188065e+001, H=1.41430809e+000, I=-2.24827851e-004, J=9.29147915e-005, CPcor=-9.57000000e-008, CTcor=3.2500e-006, WBOTC=0.00000000e+000, Slope=1.00000000, Offset=0.00000
   * - **SENSOR_PRES_0657**
     - - long_name = Paroscientific Digiquartz depth sensor sensor metadata
       - sensor_model = Paroscientific Digiquartz depth sensor
       - sensor_maker = Paroscientific Inc.
       - serial_number = 0657
       - calibration_date = 2022-09-15
       - channel = 3
     - - **Type**: http://vocab.nerc.ac.uk/collection/L05/current/138/
       - **Model**: https://vocab.nerc.ac.uk/collection/L22/current/TOOL0931/
       - **Maker**: http://vocab.nerc.ac.uk/collection/L35/current/MAN0049/
     - - **PRESSURE**: C1=-4.123534e+004, C2=-1.722041e-001, C3=1.093950e-002, D1=3.387800e-002, D2=0.000000e+000, T1=2.994183e+001, T2=-3.042465e-004, T3=3.248800e-006, T4=5.867120e-009, T5=0.000000e+000, AD590M=1.285350e-002, AD590B=-9.185990e+000, Slope=1.00001000, Offset=-0.69840
   * - **SENSOR_TEMP_4156**
     - - long_name = Sea-Bird SBE 3plus temperature sensor sensor metadata
       - sensor_model = Sea-Bird SBE 3plus temperature sensor
       - sensor_maker = Sea-Bird Scientific
       - serial_number = 4156
       - calibration_date = 2022-10-07
       - channel = 4
     - - **Type**: http://vocab.nerc.ac.uk/collection/L05/current/134/
       - **Model**: https://vocab.nerc.ac.uk/collection/L22/current/TOOL0416/
       - **Maker**: http://vocab.nerc.ac.uk/collection/L35/current/MAN0013/
     - - **TEMPERATURE**: G=4.38528002e-003, H=6.50520611e-004, I=2.37762971e-005, J=2.14313796e-006, Slope=1.00000000, Offset=0.0000
   * - **SENSOR_TEMP_4456**
     - - long_name = Sea-Bird SBE 3plus temperature sensor sensor metadata
       - sensor_model = Sea-Bird SBE 3plus temperature sensor
       - sensor_maker = Sea-Bird Scientific
       - serial_number = 4456
       - calibration_date = 2022-11-24
       - channel = 1
     - - **Type**: http://vocab.nerc.ac.uk/collection/L05/current/134/
       - **Model**: https://vocab.nerc.ac.uk/collection/L22/current/TOOL0416/
       - **Maker**: http://vocab.nerc.ac.uk/collection/L35/current/MAN0013/
     - - **TEMPERATURE**: G=4.42076714e-003, H=6.43481928e-004, I=2.23950918e-005, J=1.98540001e-006, Slope=1.00000000, Offset=0.0000


Processing Protocol
^^^^^^^^^^^^^^^^^^

This section documents the processing pipeline applied to transform the raw data.

**Pipeline Stages Applied:**

1. mapping
2. unit_handling
3. derivation
4. metadata_extraction
5. metadata_enrichment
6. validation
7. finalization

**Handlers Applied:**

- mapping:default_mapping
- mapping:regex_mapping
- unit_handling:normalize
- derivation:density
- derivation:depth
- derivation:potential_temperature
- derivation:conservative_temperature
- derivation:speed_of_sound
- metadata_extraction:attributes
- metadata_extraction:global_attributes
- metadata_enrichment:cf
- metadata_enrichment:acdd
- metadata_enrichment:acdd_auto
- metadata_enrichment:whp
- metadata_enrichment:user_metadata
- validation:cf
- validation:unit
- finalization:raw_metadata
- finalization:processor_metadata
- finalization:global_attributes
- finalization:sorting

**Variable Name Mappings:**

- ``c0mS/cm`` → ``conductivity_1``
- ``c1mS/cm`` → ``conductivity_2``
- ``prDM`` → ``pressure``
- ``sal11`` → ``salinity``
- ``sbeox0ML/L`` → ``oxygen_1``
- ``sbeox1ML/L`` → ``oxygen_2``
- ``t090C`` → ``temperature_1``
- ``t190C`` → ``temperature_2``

**Derived Parameters:**

- density
- depth
- potential_temperature_1
- potential_temperature_2
- conservative_temperature_1
- conservative_temperature_2
- speed_of_sound

**Unit Conversions:**

- temperature_1: ITS-90, deg C -> degC
- temperature_2: ITS-90, deg C -> degC
- salinity: PSU -> 1

Global Metadata
^^^^^^^^^^^^^^^

Complete dataset metadata with processing annotations:

- **Title**: Level-1 dataset from SeaBird CNV file on 2000-01-01 within 49.71–49.71N, 45.00–45.00W (depth -3538.19–-6.94 m)
- **Summary**: Level-1 dataset decoded from SeaBird CNV file with canonical variable names and units; RAW metadata preserved verbatim; no quality control applied. Time coverage: 2000-01-01T12:28:34 to 2000-01-01T13:29:55. Spatial coverage: 49.71–49.71N, 45.00–45.00W. Depth range: -3538.19–-6.94 m. Variables include: conductivity, conservative_temperature, density, depth, oxygen, potential_temperature, pressure, salinity, and 4 more.
- **Time Coverage Start**: 2000-01-01T12:28:34
- **Time Coverage End**: 2000-01-01T13:29:55
- **Time Coverage Duration**: PT3681S
- **Time Coverage Resolution**: PT1S
- **Geospatial Lat Min**: 49.70834
- **Geospatial Lat Max**: 49.71112
- **Geospatial Lon Min**: -45.00409
- **Geospatial Lon Max**: -45.00073
- **Geospatial Vertical Min**: -3538.186649759045
- **Geospatial Vertical Max**: -6.940067223004776
- **Geospatial Vertical Positive**: down
- **Conventions**: ACDD-1.3, CF-1.13
- **Standard Name Vocabulary**: CF-1.13
- **Featuretype**: timeSeries
- **Cdm Data Type**: TimeSeries
- **Date Created**: 2026-02-13T07:44:16.059633Z
- **Date Modified**: 2026-02-13T07:44:16.059633Z
- **History**: 2026-02-13T07:44:16.059633Z - Processed by SeaSenseLib v0.4.0; Reader: SbeCnvReader; Format: SeaBird CNV; Source file: MSM121_054_1db.cnv; Stages: mapping, unit_handling, derivation, metadata_extraction, metadata_enrichment, validation, finalization; Mapped 8 variables; Derived: density, depth, potential_temperature_1, potential_temperature_2, conservative_temperature_1, conservative_temperature_2, speed_of_sound
- **Keywords**: oceanography, in situ, level-1, cnv, seabird, conductivity, conservative_temperature, density, depth, oxygen, potential_temperature
- **Raw Format**: sbe-cnv
- **Raw Filename**: MSM121_054_1db.cnv
- **Processing Level**: L1
- **Raw Filesize Bytes**: 529091
- **Raw Mtime Utc**: 2026-01-05T05:05:13.458080Z
- **Raw Sha256**: 768c3ebf1974bf629fa8d6fcb5e98479323583ea14023b207264b9c7cc121e61
- **Raw Metadata Schema**: seasenselib/raw-opaque-1.0
- **Raw Metadata**: {"schema": "seasenselib/raw-opaque-1.0", "raw_format": "sbe-cnv", "raw_filename": "MSM121_054_1db.cnv", "blocks": {"header": "* Sea-Bird SBE 9 Data File:\n* FileName = C:\\Data\\MSM121\\MSM121_054.hdr\n* Software Version Seasave V 7.22\n* Temperature SN = 4456\n* Conductivity SN = 2646\n* Number of Bytes Per Scan = 38\n* Number of Voltage Words = 3\n* Number of Scans Averaged by the Deck Unit = 1\n* System UpLoad Time = Oct 08 2023 12:26:20\n* NMEA Latitude = 49 42.50 N\n* NMEA Longitude = 045 00.04 W\n* NMEA UTC (Time) = Oct 08 2023 12:26:20\n* Store Lat/Lon Data = Append to Every Scan\n* SBE 11plus V 5.1g\n* number of scans to average = 1\n* pressure baud rate = 19200\n* NMEA baud rate = 4800\n* GPIB address = 1\n* advance primary conductivity  0.073 seconds\n* advance secondary conductivity  0.073 seconds\n* delete word 8 from scan\n* autorun on power up is disabled\n* S>\n** Ship: Maria S. Merian\n** Cruise: MSM121\n** Profile: 54\n** Station: 54\n** WaterDepth: 3550\n* System UTC = Oct 08 2023 12:26:20\n# nquan = 13\n# nvalues = 3593                        \n# units = specified\n# name 0 = timeQ: Time, NMEA [seconds]\n# name 1 = prDM: Pressure, Digiquartz [db]\n# name 2 = t090C: Temperature [ITS-90, deg C]\n# name 3 = c0mS/cm: Conductivity [mS/cm]\n# name 4 = sbeox0ML/L: Oxygen, SBE 43 [ml/l]\n# name 5 = t190C: Temperature, 2 [ITS-90, deg C]\n# name 6 = c1mS/cm: Conductivity, 2 [mS/cm]\n# name 7 = sbeox1ML/L: Oxygen, SBE 43, 2 [ml/l]\n# name 8 = latitude: Latitude [deg]\n# name 9 = longitude: Longitude [deg]\n# name 10 = timeS: Time, Elapsed [seconds]\n# name 11 = sal11: Salinity, Practical, 2 [PSU]\n# name 12 = flag: flag\n# span 0 =  750083314,  750086995       \n# span 1 =      7.000,   3599.000       \n# span 2 =     1.9441,    14.2864       \n# span 3 =  32.109489,  41.580563       \n# span 4 =     4.3448,     6.9701       \n# span 5 =     1.9433,    14.2855       \n# span 6 =  32.108106,  41.579826       \n# span 7 =     4.2256,     6.8076       \n# span 8 =   49.70834,   49.71112       \n# span 9 =  -45.00409,  -45.00073       \n# span 10 =    134.461,   3815.453      \n# span 11 =    33.9944,    34.9173      \n# span 12 = 0.0000e+00, 0.0000e+00      \n# interval = decibars: 1                \n# start_time = Jan 01 2000 12:26:20 [NMEA time, first data scan]\n# bad_flag = -9.990e-29\n# <Sensors count=\"11\" >\n#   <sensor Channel=\"1\" >\n#     <!-- Frequency 0, Temperature -->\n#     <TemperatureSensor SensorID=\"55\" >\n#       <SerialNumber>4456</SerialNumber>\n#       <CalibrationDate>24-Nov-22</CalibrationDate>\n#       <UseG_J>1</UseG_J>\n#       <A>0.00000000e+000</A>\n#       <B>0.00000000e+000</B>\n#       <C>0.00000000e+000</C>\n#       <D>0.00000000e+000</D>\n#       <F0_Old>0.000</F0_Old>\n#       <G>4.42076714e-003</G>\n#       <H>6.43481928e-004</H>\n#       <I>2.23950918e-005</I>\n#       <J>1.98540001e-006</J>\n#       <F0>1000.000</F0>\n#       <Slope>1.00000000</Slope>\n#       <Offset>0.0000</Offset>\n#     </TemperatureSensor>\n#   </sensor>\n#   <sensor Channel=\"2\" >\n#     <!-- Frequency 1, Conductivity -->\n#     <ConductivitySensor SensorID=\"3\" >\n#       <SerialNumber>2646</SerialNumber>\n#       <CalibrationDate>27-Oct-22</CalibrationDate>\n#       <UseG_J>1</UseG_J>\n#       <!-- Cell const and series R are applicable only for wide range sensors. -->\n#       <SeriesR>0.0000</SeriesR>\n#       <CellConst>2000.0000</CellConst>\n#       <ConductivityType>0</ConductivityType>\n#       <Coefficients equation=\"0\" >\n#         <A>0.00000000e+000</A>\n#         <B>0.00000000e+000</B>\n#         <C>0.00000000e+000</C>\n#         <D>0.00000000e+000</D>\n#         <M>0.0</M>\n#         <CPcor>-9.57000000e-008</CPcor>\n#       </Coefficients>\n#       <Coefficients equation=\"1\" >\n#         <G>-1.03188065e+001</G>\n#         <H>1.41430809e+000</H>\n#         <I>-2.24827851e-004</I>\n#         <J>9.29147915e-005</J>\n#         <CPcor>-9.57000000e-008</CPcor>\n#         <CTcor>3.2500e-006</CTcor>\n#         <!-- WBOTC not applicable unless ConductivityType = 1. -->\n#         <WBOTC>0.00000000e+000</WBOTC>\n#       </Coefficients>\n#       <Slope>1.00000000</Slope>\n#       <Offset>0.00000</Offset>\n#     </ConductivitySensor>\n#   </sensor>\n#   <sensor Channel=\"3\" >\n#     <!-- Frequency 2, Pressure, Digiquartz with TC -->\n#     <PressureSensor SensorID=\"45\" >\n#       <SerialNumber>0657</SerialNumber>\n#       <CalibrationDate>15-Sep-22</CalibrationDate>\n#       <C1>-4.123534e+004</C1>\n#       <C2>-1.722041e-001</C2>\n#       <C3>1.093950e-002</C3>\n#       <D1>3.387800e-002</D1>\n#       <D2>0.000000e+000</D2>\n#       <T1>2.994183e+001</T1>\n#       <T2>-3.042465e-004</T2>\n#       <T3>3.248800e-006</T3>\n#       <T4>5.867120e-009</T4>\n#       <Slope>1.00001000</Slope>\n#       <Offset>-0.69840</Offset>\n#       <T5>0.000000e+000</T5>\n#       <AD590M>1.285350e-002</AD590M>\n#       <AD590B>-9.185990e+000</AD590B>\n#     </PressureSensor>\n#   </sensor>\n#   <sensor Channel=\"4\" >\n#     <!-- Frequency 3, Temperature, 2 -->\n#     <TemperatureSensor SensorID=\"55\" >\n#       <SerialNumber>4156</SerialNumber>\n#       <CalibrationDate>07-Oct-22</CalibrationDate>\n#       <UseG_J>1</UseG_J>\n#       <A>0.00000000e+000</A>\n#       <B>0.00000000e+000</B>\n#       <C>0.00000000e+000</C>\n#       <D>0.00000000e+000</D>\n#       <F0_Old>0.000</F0_Old>\n#       <G>4.38528002e-003</G>\n#       <H>6.50520611e-004</H>\n#       <I>2.37762971e-005</I>\n#       <J>2.14313796e-006</J>\n#       <F0>1000.000</F0>\n#       <Slope>1.00000000</Slope>\n#       <Offset>0.0000</Offset>\n#     </TemperatureSensor>\n#   </sensor>\n#   <sensor Channel=\"5\" >\n#     <!-- Frequency 4, Conductivity, 2 -->\n#     <ConductivitySensor SensorID=\"3\" >\n#       <SerialNumber>2643</SerialNumber>\n#       <CalibrationDate>27-Oct-22</CalibrationDate>\n#       <UseG_J>1</UseG_J>\n#       <!-- Cell const and series R are applicable only for wide range sensors. -->\n#       <SeriesR>0.0000</SeriesR>\n#       <CellConst>2000.0000</CellConst>\n#       <ConductivityType>0</ConductivityType>\n#       <Coefficients equation=\"0\" >\n#         <A>0.00000000e+000</A>\n#         <B>0.00000000e+000</B>\n#         <C>0.00000000e+000</C>\n#         <D>0.00000000e+000</D>\n#         <M>0.0</M>\n#         <CPcor>-9.57000000e-008</CPcor>\n#       </Coefficients>\n#       <Coefficients equation=\"1\" >\n#         <G>-9.90089056e+000</G>\n#         <H>1.37876824e+000</H>\n#         <I>-2.09415484e-003</I>\n#         <J>2.10319217e-004</J>\n#         <CPcor>-9.57000000e-008</CPcor>\n#         <CTcor>3.2500e-006</CTcor>\n#         <!-- WBOTC not applicable unless ConductivityType = 1. -->\n#         <WBOTC>0.00000000e+000</WBOTC>\n#       </Coefficients>\n#       <Slope>1.00000000</Slope>\n#       <Offset>0.00000</Offset>\n#     </ConductivitySensor>\n#   </sensor>\n#   <sensor Channel=\"6\" >\n#     <!-- A/D voltage 0, Oxygen, SBE 43 -->\n#     <OxygenSensor SensorID=\"38\" >\n#       <SerialNumber>0547</SerialNumber>\n#       <CalibrationDate>26-Oct-22</CalibrationDate>\n#       <Use2007Equation>1</Use2007Equation>\n#       <CalibrationCoefficients equation=\"0\" >\n#         <!-- Coefficients for Owens-Millard equation. -->\n#         <Boc>0.0000</Boc>\n#         <Soc>0.0000e+000</Soc>\n#         <offset>0.0000</offset>\n#         <Pcor>0.00e+000</Pcor>\n#         <Tcor>0.0000</Tcor>\n#         <Tau>0.0</Tau>\n#       </CalibrationCoefficients>\n#       <CalibrationCoefficients equation=\"1\" >\n#         <!-- Coefficients for Sea-Bird equation - SBE calibration in 2007 and later. -->\n#         <Soc>4.7067e-001</Soc>\n#         <offset>-0.4872</offset>\n#         <A>-4.8884e-003</A>\n#         <B> 2.3084e-004</B>\n#         <C>-3.2714e-006</C>\n#         <D0> 2.5826e+000</D0>\n#         <D1> 1.92634e-004</D1>\n#         <D2>-4.64803e-002</D2>\n#         <E> 3.6000e-002</E>\n#         <Tau20> 1.3400</Tau20>\n#         <H1>-3.3000e-002</H1>\n#         <H2> 5.0000e+003</H2>\n#         <H3> 1.4500e+003</H3>\n#       </CalibrationCoefficients>\n#     </OxygenSensor>\n#   </sensor>\n#   <sensor Channel=\"7\" >\n#     <!-- A/D voltage 1, Free -->\n#   </sensor>\n#   <sensor Channel=\"8\" >\n#     <!-- A/D voltage 2, Altimeter -->\n#     <AltimeterSensor SensorID=\"0\" >\n#       <SerialNumber>79774</SerialNumber>\n#       <CalibrationDate>10/12/2021</CalibrationDate>\n#       <ScaleFactor>15.000</ScaleFactor>\n#       <Offset>0.000</Offset>\n#     </AltimeterSensor>\n#   </sensor>\n#   <sensor Channel=\"9\" >\n#     <!-- A/D voltage 3, Free -->\n#   </sensor>\n#   <sensor Channel=\"10\" >\n#     <!-- A/D voltage 4, Oxygen, SBE 43, 2 -->\n#     <OxygenSensor SensorID=\"38\" >\n#       <SerialNumber>0267</SerialNumber>\n#       <CalibrationDate>11-Oct-22</CalibrationDate>\n#       <Use2007Equation>1</Use2007Equation>\n#       <CalibrationCoefficients equation=\"0\" >\n#         <!-- Coefficients for Owens-Millard equation. -->\n#         <Boc>0.0000</Boc>\n#         <Soc>0.0000e+000</Soc>\n#         <offset>0.0000</offset>\n#         <Pcor>0.00e+000</Pcor>\n#         <Tcor>0.0000</Tcor>\n#         <Tau>0.0</Tau>\n#       </CalibrationCoefficients>\n#       <CalibrationCoefficients equation=\"1\" >\n#         <!-- Coefficients for Sea-Bird equation - SBE calibration in 2007 and later. -->\n#         <Soc>5.2013e-001</Soc>\n#         <offset>-0.5920</offset>\n#         <A>-4.5577e-003</A>\n#         <B> 1.3388e-004</B>\n#         <C>-2.1032e-006</C>\n#         <D0> 2.5826e+000</D0>\n#         <D1> 1.92634e-004</D1>\n#         <D2>-4.64803e-002</D2>\n#         <E> 3.6000e-002</E>\n#         <Tau20> 1.5400</Tau20>\n#         <H1>-3.3000e-002</H1>\n#         <H2> 5.0000e+003</H2>\n#         <H3> 1.4500e+003</H3>\n#       </CalibrationCoefficients>\n#     </OxygenSensor>\n#   </sensor>\n#   <sensor Channel=\"11\" >\n#     <!-- A/D voltage 5, Free -->\n#   </sensor>\n# </Sensors>\n# datcnv_date = Oct 08 2023 14:25:30, 7.22.0 [datcnv_vars = 12]\n# datcnv_in = C:\\Data\\MSM121\\MSM121_054.hex C:\\Data\\MSM121\\MSM121_012.XMLCON\n# datcnv_skipover = 0\n# datcnv_ox_hysteresis_correction = yes\n# datcnv_ox_tau_correction = no\n# filter_date = Oct 09 2023 11:05:09, 7.26.7.129\n# filter_in = C:\\Users\\rsteinf\\daten\\msm121\\ctdraw\\MSM121_054.cnv\n# filter_low_pass_tc_A = 0.150\n# filter_low_pass_tc_B = 0.500\n# filter_low_pass_A_vars = prDM sal11\n# filter_low_pass_B_vars = sbeox0ML/L sbeox1ML/L\n# alignctd_date = Oct 09 2023 11:06:03, 7.26.7.129\n# alignctd_in = C:\\Users\\rsteinf\\daten\\msm121\\ctd\\MSM121_054.cnv\n# alignctd_adv = sbeox0ML/L 4.000, sbeox1ML/L 4.000                                                                                                                                                                                  \n# celltm_date = Oct 09 2023 11:06:32, 7.26.7.129\n# celltm_in = C:\\Users\\rsteinf\\daten\\msm121\\ctd\\MSM121_054.cnv\n# celltm_alpha = 0.0300, 0.0300\n# celltm_tau = 7.0000, 7.0000\n# celltm_temp_sensor_use_for_cond = primary, secondary\n# loopedit_date = Oct 09 2023 11:07:20, 7.26.7.129\n# loopedit_in = C:\\Users\\rsteinf\\daten\\msm121\\ctd\\MSM121_054.cnv\n# loopedit_minVelocity = 0.100                                                                                            \n# loopedit_surfaceSoak: minDepth = 7.0, maxDepth = 24, useDeckPress = 1                                                   \n# loopedit_excl_bad_scans = yes\n# wildedit_date = Oct 09 2023 11:07:53, 7.26.7.129\n# wildedit_in = C:\\Users\\rsteinf\\daten\\msm121\\ctd\\MSM121_054.cnv\n# wildedit_pass1_nstd = 2.0\n# wildedit_pass2_nstd = 20.0\n# wildedit_pass2_mindelta = 0.000e+000\n# wildedit_npoint = 100\n# wildedit_vars = prDM t090C c0mS/cm sbeox0ML/L t190C c1mS/cm sbeox1ML/L sal11\n# wildedit_excl_bad_scans = yes\n# binavg_date = Oct 09 2023 11:08:19, 7.26.7.129\n# binavg_in = C:\\Users\\rsteinf\\daten\\msm121\\ctd\\MSM121_054.cnv\n# binavg_bintype = decibars\n# binavg_binsize = 1\n# binavg_excl_bad_scans = yes\n# binavg_skipover = 0\n# binavg_omit = 0\n# binavg_min_scans_bin = 1\n# binavg_max_scans_bin = 2147483647\n# binavg_surface_bin = yes, min = 0.000, max = 0.000, value = 0.000\n# file_type = ascii\n*END*", "calibration": null, "configuration": null, "other": {"global_attributes": {"latitude": 49.708333333333336, "longitude": -45.00066666666667, "CreateTime": "2026-02-13T08:44:15.988843+01:00", "CreateTime_UTC": "2026-02-13T07:44:15.988843Z", "DataType": "TimeSeries", "cnv_sbe_model": "SBE 9", "cnv_software_version": "Seasave V 7.22", "cnv_start_date": "2023-10-08 12:26:20", "cnv_upload_date": "2023-10-08 12:26:20", "cnv_nmea_date": "2023-10-08 12:26:20", "cnv_sensor_1": {"channel": 1, "sensor_type": "TemperatureSensor", "serial_number": "4456", "calibration_date": "24-Nov-22", "sensor_id": "55"}, "cnv_sensor_2": {"channel": 2, "sensor_type": "ConductivitySensor", "serial_number": "2646", "calibration_date": "27-Oct-22", "sensor_id": "3"}, "cnv_sensor_3": {"channel": 3, "sensor_type": "PressureSensor", "serial_number": "0657", "calibration_date": "15-Sep-22", "sensor_id": "45"}, "cnv_sensor_4": {"channel": 4, "sensor_type": "TemperatureSensor", "serial_number": "4156", "calibration_date": "07-Oct-22", "sensor_id": "55"}, "cnv_sensor_5": {"channel": 5, "sensor_type": "ConductivitySensor", "serial_number": "2643", "calibration_date": "27-Oct-22", "sensor_id": "3"}, "cnv_sensor_6": {"channel": 6, "sensor_type": "OxygenSensor", "serial_number": "0547", "calibration_date": "26-Oct-22", "sensor_id": "38"}, "cnv_sensor_7": {"channel": 7}, "cnv_sensor_8": {"channel": 8, "sensor_type": "AltimeterSensor", "serial_number": "79774", "calibration_date": "10/12/2021", "sensor_id": "0"}, "cnv_sensor_9": {"channel": 9}, "cnv_sensor_10": {"channel": 10, "sensor_type": "OxygenSensor", "serial_number": "0267", "calibration_date": "11-Oct-22", "sensor_id": "38"}, "cnv_sensor_11": {"channel": 11}, "source_format_name": "SeaBird CNV", "acdd_autogen_fields": "title,summary,keywords"}, "variables": {}}}}
- **Processor Name**: SeaSenseLib
- **Processor Version**: 0.4.0
- **Processor Level**: L1
- **Processor Module**: seasenselib.readers.sbe_cnv_reader
- **Processor Module Name**: SeaBird CNV
- **Processor Module Key**: sbe-cnv
- **Processor Runtime**: CPython
- **Processor Runtime Version**: 3.11.7
- **Processor Execution Time Utc**: 2026-02-13T07:44:16.059616Z
- **Processor Machine**: MacBookPro
- **Processor Os**: Darwin 25.2.0
