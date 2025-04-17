import numpy as np
import time
from smbus2 import SMBus
import Jetson.GPIO as GPIO
import serial 

from pir_functions import PIR
from accel_functions import accel

ser = serial.Serial('/dev/ttyTHS1', 38400, timeout=1)

positions = [1735, 649, 1395, 415, 1170, 1592, 846, 120, 319, 1558,
977, 248, 503, 721, 1252, 1802, 1141, 835, 1417, 1569,
93, 1034, 681, 1746, 155, 1305, 115, 1551, 1109, 1654,
48, 1212, 891, 1687, 1083, 1739, 349, 179, 1318, 341,
814, 1470, 200, 57, 145, 596, 366, 848, 1268, 637,
1320, 132, 1471, 1013, 1024, 1693, 434, 1449, 826, 1634,
1597, 1846, 1309, 1730, 56, 1270, 866, 1195, 771, 336,
703, 1624, 1561, 1801, 697, 1423, 1381, 1156, 1526, 798,
1372, 1064, 486, 592, 831, 1787, 513, 1175, 326, 1652,
74, 1547, 450, 1278, 22, 398, 1771, 343, 1803, 1111
]

a_c = accel()

a_c.enable_logging(True)

bus_num_accel = 1 
#start the bus
bus_accel = SMBus(bus_num_accel)

bus_accel.write_byte_data(0x18, 0x15, 0x00) #0x15 is a config reg, 0x00 sets to active. 0x18 is accel address
bus_accel.write_byte_data(0x18, 0x17, 0x50)
bus_accel.write_byte_data(0x18, 0x15, 0x01) #0x15 is a config reg, 0x01 sets to active. 0x18 is accel address

a_c.basis(bus_accel)

mt = time.time()

for i in range(0,50):
    print(i)
    while mt > (time.time() - 7):
        a_c.check_accel(bus_accel,mt)
        time.sleep(0.01)
    
    pos = positions[i]
    hex_value = f"{pos:03X}"[-3:] #hex val of pan 
    command = f"CO0{hex_value}\n" #full command value


    # Send the command over serial
    #print("sent command ",command)
    ser.write(command.encode('UTF-8'))
    response = ser.readline()
    #print("received response ", response)
    hexpos= int(response.strip(), 16)

    mt = time.time()

    

