"""AirNode S3 — single source of truth: parts, nets, footprints, schematic placement.

Board: ESP32-S3 environmental sensor node, USB-C powered, native USB, BME280,
Qwiic/STEMMA-QT I2C port, UART debug header, 6x GPIO breakout.
"""
NC = None  # explicit no-connect

POWER_NETS = {'GND': 'power:GND', '+3V3': 'power:+3V3', 'VBUS': 'power:VBUS'}

# Each part: ref, lib symbol, value, footprint, schematic position (mm), pin->net, MPN
PARTS = [
    # ---------------- USB-C input & protection ----------------
    dict(ref='J1', lib='Connector:USB_C_Receptacle_USB2.0_16P', value='USB_C',
         fp='Connector_USB:USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal', at=(48.26, 91.44),
         mpn='GCT USB4105-GF-A',
         nets={'A1': 'GND', 'A12': 'GND', 'B1': 'GND', 'B12': 'GND', 'S1': 'GND',
               'A4': 'VBUS_IN', 'A9': 'VBUS_IN', 'B4': 'VBUS_IN', 'B9': 'VBUS_IN',
               'A5': 'CC1', 'B5': 'CC2', 'A6': 'USB_DP', 'B6': 'USB_DP',
               'A7': 'USB_DN', 'B7': 'USB_DN', 'A8': NC, 'B8': NC}),
    dict(ref='R1', lib='Device:R', value='5.1k', fp='Resistor_SMD:R_0603_1608Metric',
         at=(86.36, 114.3), nets={'1': 'CC1', '2': 'GND'}),
    dict(ref='R2', lib='Device:R', value='5.1k', fp='Resistor_SMD:R_0603_1608Metric',
         at=(99.06, 114.3), nets={'1': 'CC2', '2': 'GND'}),
    dict(ref='F1', lib='Device:Polyfuse', value='500mA', fp='Fuse:Fuse_1206_3216Metric',
         at=(101.6, 55.88), mpn='Littelfuse 1206L050YR', nets={'1': 'VBUS_IN', '2': 'VBUS'}),
    dict(ref='U3', lib='Power_Protection:USBLC6-2SC6', value='USBLC6-2SC6',
         fp='Package_TO_SOT_SMD:SOT-23-6', at=(127.0, 99.06), mpn='ST USBLC6-2SC6',
         nets={'1': 'USB_DP', '6': 'USB_DP', '3': 'USB_DN', '4': 'USB_DN', '5': 'VBUS', '2': 'GND'}),

    # ---------------- 3.3 V regulator ----------------
    dict(ref='U2', lib='Regulator_Linear:AP2112K-3.3', value='AP2112K-3.3',
         fp='Package_TO_SOT_SMD:SOT-23-5', at=(208.28, 60.96), mpn='Diodes AP2112K-3.3TRG1',
         nets={'1': 'VBUS', '3': 'VBUS', '2': 'GND', '5': '+3V3', '4': NC}),
    dict(ref='C1', lib='Device:C', value='10uF', fp='Capacitor_SMD:C_0805_2012Metric',
         at=(180.34, 68.58), nets={'1': 'VBUS', '2': 'GND'}),
    dict(ref='C2', lib='Device:C', value='10uF', fp='Capacitor_SMD:C_0805_2012Metric',
         at=(236.22, 68.58), nets={'1': '+3V3', '2': 'GND'}),

    # ---------------- ESP32-S3 ----------------
    dict(ref='U1', lib='RF_Module:ESP32-S3-WROOM-1', value='ESP32-S3-WROOM-1-N8',
         fp='RF_Module:ESP32-S3-WROOM-1', at=(238.76, 177.8), mpn='Espressif ESP32-S3-WROOM-1-N8',
         nets={'1': 'GND', '40': 'GND', '41': 'GND', '2': '+3V3', '3': 'EN',
               '27': 'BOOT', '13': 'USB_DN', '14': 'USB_DP',
               '12': 'I2C_SDA', '17': 'I2C_SCL', '38': 'LED_STAT',
               '37': 'U0TXD', '36': 'U0RXD',
               '4': 'GPIO4', '5': 'GPIO5', '6': 'GPIO6', '7': 'GPIO7', '8': 'GPIO15', '9': 'GPIO16',
               # unused
               '10': NC, '11': NC, '15': NC, '16': NC, '18': NC, '19': NC, '20': NC, '21': NC,
               '22': NC, '23': NC, '24': NC, '25': NC, '26': NC, '28': NC, '29': NC, '30': NC,
               '31': NC, '32': NC, '33': NC, '34': NC, '35': NC, '39': NC}),
    dict(ref='C3', lib='Device:C', value='10uF', fp='Capacitor_SMD:C_0805_2012Metric',
         at=(190.5, 134.62), nets={'1': '+3V3', '2': 'GND'}),
    dict(ref='C4', lib='Device:C', value='100nF', fp='Capacitor_SMD:C_0603_1608Metric',
         at=(203.2, 134.62), nets={'1': '+3V3', '2': 'GND'}),

    # ---------------- Reset / boot ----------------
    dict(ref='R3', lib='Device:R', value='10k', fp='Resistor_SMD:R_0603_1608Metric',
         at=(38.1, 182.88), nets={'1': '+3V3', '2': 'EN'}),
    dict(ref='C5', lib='Device:C', value='1uF', fp='Capacitor_SMD:C_0603_1608Metric',
         at=(53.34, 182.88), nets={'1': 'EN', '2': 'GND'}),
    dict(ref='SW1', lib='Switch:SW_Push', value='RESET', fp='Button_Switch_SMD:SW_SPST_TL3342',
         at=(76.2, 182.88), mpn='E-Switch TL3342F160QG', nets={'1': 'EN', '2': 'GND'}),
    dict(ref='R4', lib='Device:R', value='10k', fp='Resistor_SMD:R_0603_1608Metric',
         at=(101.6, 182.88), nets={'1': '+3V3', '2': 'BOOT'}),
    dict(ref='SW2', lib='Switch:SW_Push', value='BOOT', fp='Button_Switch_SMD:SW_SPST_TL3342',
         at=(124.46, 182.88), mpn='E-Switch TL3342F160QG', nets={'1': 'BOOT', '2': 'GND'}),

    # ---------------- Indicators ----------------
    dict(ref='R5', lib='Device:R', value='1k', fp='Resistor_SMD:R_0603_1608Metric',
         at=(38.1, 236.22), nets={'1': '+3V3', '2': 'LED_PWR'}),
    dict(ref='D1', lib='Device:LED', value='GREEN', fp='LED_SMD:LED_0603_1608Metric',
         at=(58.42, 243.84), nets={'2': 'LED_PWR', '1': 'GND'}),
    dict(ref='R6', lib='Device:R', value='1k', fp='Resistor_SMD:R_0603_1608Metric',
         at=(96.52, 236.22), nets={'1': 'LED_STAT', '2': 'LED_STAT_R'}),
    dict(ref='D2', lib='Device:LED', value='BLUE', fp='LED_SMD:LED_0603_1608Metric',
         at=(116.84, 243.84), nets={'2': 'LED_STAT_R', '1': 'GND'}),

    # ---------------- Sensor & I2C ----------------
    dict(ref='U4', lib='Sensor:BME280', value='BME280',
         fp='Package_LGA:Bosch_LGA-8_2.5x2.5mm_P0.65mm_ClockwisePinNumbering',
         at=(337.82, 81.28), mpn='Bosch BME280',
         nets={'1': 'GND', '7': 'GND', '6': '+3V3', '8': '+3V3', '2': '+3V3',
               '3': 'I2C_SDA', '4': 'I2C_SCL', '5': 'GND'}),
    dict(ref='C6', lib='Device:C', value='100nF', fp='Capacitor_SMD:C_0603_1608Metric',
         at=(312.42, 63.5), nets={'1': '+3V3', '2': 'GND'}),
    dict(ref='R7', lib='Device:R', value='4.7k', fp='Resistor_SMD:R_0603_1608Metric',
         at=(383.54, 78.74), nets={'1': '+3V3', '2': 'I2C_SDA'}),
    dict(ref='R8', lib='Device:R', value='4.7k', fp='Resistor_SMD:R_0603_1608Metric',
         at=(396.24, 78.74), nets={'1': '+3V3', '2': 'I2C_SCL'}),
    dict(ref='J2', lib='Connector_Generic:Conn_01x04', value='Qwiic',
         fp='Connector_JST:JST_SH_SM04B-SRSS-TB_1x04-1MP_P1.00mm_Horizontal',
         at=(355.6, 129.54), mpn='JST SM04B-SRSS-TB',
         nets={'1': 'GND', '2': '+3V3', '3': 'I2C_SDA', '4': 'I2C_SCL'}),

    # ---------------- Expansion & debug ----------------
    dict(ref='J3', lib='Connector_Generic:Conn_01x04', value='UART',
         fp='Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical',
         at=(342.9, 182.88), nets={'1': 'GND', '2': 'U0TXD', '3': 'U0RXD', '4': '+3V3'}),
    dict(ref='J4', lib='Connector_Generic:Conn_01x08', value='GPIO',
         fp='Connector_PinHeader_2.54mm:PinHeader_1x08_P2.54mm_Vertical',
         at=(342.9, 223.52),
         nets={'1': '+3V3', '2': 'GPIO4', '3': 'GPIO5', '4': 'GPIO6', '5': 'GPIO7',
               '6': 'GPIO15', '7': 'GPIO16', '8': 'GND'}),

    # ---------------- Mechanical ----------------
    dict(ref='H1', lib='Mechanical:MountingHole', value='M2.5', fp='MountingHole:MountingHole_2.7mm_M2.5', at=(381.0, 177.8), nets={}),
    dict(ref='H2', lib='Mechanical:MountingHole', value='M2.5', fp='MountingHole:MountingHole_2.7mm_M2.5', at=(396.24, 177.8), nets={}),
    dict(ref='H3', lib='Mechanical:MountingHole', value='M2.5', fp='MountingHole:MountingHole_2.7mm_M2.5', at=(381.0, 193.04), nets={}),
    dict(ref='H4', lib='Mechanical:MountingHole', value='M2.5', fp='MountingHole:MountingHole_2.7mm_M2.5', at=(396.24, 193.04), nets={}),
]

# Power flags (net, position of the power symbol)
PWR_FLAGS = [('VBUS', (167.64, 48.26)), ('GND', (167.64, 71.12))]

# Schematic block frames: (title, x1, y1, x2, y2)
BLOCKS = [
    ('USB-C INPUT & PROTECTION', 20.32, 35.56, 152.4, 147.32),
    ('3.3 V LDO REGULATOR', 160.02, 35.56, 254.0, 99.06),
    ('ESP32-S3 MCU (native USB)', 160.02, 109.22, 297.18, 260.35),
    ('RESET / BOOT', 20.32, 157.48, 152.4, 210.82),
    ('STATUS LEDS', 20.32, 220.98, 152.4, 260.35),
    ('BME280 SENSOR & QWIIC I2C', 302.26, 35.56, 411.48, 147.32),
    ('DEBUG & GPIO EXPANSION', 302.26, 157.48, 411.48, 246.38),
]

NOTES = [
    ((22.86, 142.24), 'CC1/CC2 5.1k pull-downs = USB-C sink, up to 5V/3A advertised.\nUSBLC6 clamps ESD on D+/D- right at the connector.'),
    ((162.56, 93.98), 'AP2112K: 600mA LDO, 250mV dropout. ESP32-S3 Wi-Fi TX peaks ~355mA.'),
    ((162.56, 254.0), 'GPIO19/20 = native USB D-/D+ (flashing + CDC serial, no USB-UART chip).\nIO0 low at reset = download mode.'),
    ((304.8, 142.24), 'BME280 in I2C mode (CSB high), SDO low -> address 0x76. Qwiic pinout: GND, 3V3, SDA, SCL.'),
]
