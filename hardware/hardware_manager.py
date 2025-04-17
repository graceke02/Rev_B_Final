import numpy as np
import time
from smbus2 import SMBus
import Jetson.GPIO as GPIO

from pir_functions import PIR
from accel_functions import accel

#gpio_flags = {"pir1_flag" : False, "pir2_flag":False, "pir3_flag":False, "pir_time":0, "accel_flag":False}


#hardware hangdler is for calling and processing PIR and accel 
def hardware_handler(gpio_flags, batt_symbol, lock, command_queue, basis_queue, config, config_lock, move_time_queue):
    #gpio flags are multiprocessing dict
    #lock to make sure gpio dict is good 

    print("Start hardware manager")
    
    #set buses for i2c
    bus_num_pir = 7
    bus_pir  = SMBus(bus_num_pir)

    bus_num_accel = 1 
    #start the bus
    bus_accel = SMBus(bus_num_accel)

    #set up gpio for battery
    GPIO.cleanup()
    GPIO.setmode(GPIO.BOARD)
    
    battery_pin = 33 #31 or 33, just depends on what we do 
    GPIO.setup(battery_pin, GPIO.IN)

    bus_accel.write_byte_data(0x18, 0x15, 0x00) #0x15 is a config reg, 0x00 sets to active. 0x18 is accel address
    bus_accel.write_byte_data(0x18, 0x17, 0x50)
    bus_accel.write_byte_data(0x18, 0x15, 0x01) #0x15 is a config reg, 0x01 sets to active. 0x18 is accel address


    #instantiate pir and accel class
    p_c = PIR()
    a_c = accel()

    a_c.accel_flag_write(False)
    
    mt = 0
    #accel basis
    #a_c.basis(bus_accel)
    #print(a_c.y_tol_l, a_c.y_tol_u, a_c.z_tol_l, a_c.z_tol_u)
    #time.sleep(3)

    #get initial battery 
    b_l = [1]*20

    #gpio_flags["accel_flag"] = False
    #a_c.enable_logging(True)

    while True:
        if not(gpio_flags["accel_flag"]): #only update pir values while accel is false. If tampering is true, then DO NOT WANT TO KEEP CHECKING ACCEL
            #update pir flags
            a_c.enable_logging(True)
            with lock:
                #check accel 
                if not move_time_queue.empty():
                    mt = move_time_queue.get()
                gpio_flags["accel_flag"] = a_c.check_accel(bus_accel,mt) #check accel
                gpio_flags["pir1_flag"], gpio_flags["pir2_flag"], gpio_flags["pir3_flag"], gpio_flags["pir_time"] = p_c.read(bus_pir)
                #print(gpio_flags["pir1_flag"], gpio_flags["pir2_flag"], gpio_flags["pir3_flag"], gpio_flags["pir_time"])
                #print((gpio_flags["pir1_flag"] or gpio_flags["pir2_flag"] or gpio_flags["pir3_flag"]))
                pir_pos = p_c.pan_to_sensor()
                with config_lock:
                    m_allow = config["motion_allowed"] and config["cam_on"]
                #print("pir pos and config = ", pir_pos, m_allow)
                if (pir_pos != None) and m_allow:
                    command_queue.put(("motion_detection", pir_pos))

        else:
            with lock:
                gpio_flags["pir1_flag"], gpio_flags["pir2_flag"], gpio_flags["pir3_flag"] = False,False,False
            with config_lock:
                config["correct_prop_lines"] = False

        
        b_l.pop(0)
        b_l.append((GPIO.input(battery_pin)))

        with lock:
            if 0 in b_l: 
                batt_symbol.value = 1 #in sams app 1 is battery being used
            else:
                batt_symbol.value = 0

        if not(basis_queue.empty()):
            basis_queue.get()
            a_c.basis(bus_accel)
            with lock:
                gpio_flags["accel_flag"] = False
            a_c.accel_flag_write(False)
        #sleep to realease and free up core for a hot sec
        #only need to read 20 times a second 
        time.sleep(0.01)
    



        


    

