import cv2
import numpy as np
import time
from smbus2 import SMBus
import datetime
import serial
import csv
import os
from scipy.signal import butter, filtfilt
from scipy.signal import butter, lfilter_zi, lfilter

class accel:
    address = 0x18
    #accel accounting for instability
    not_random_count = 3 #number of consecutive triggers to be not random

    #accel basis
    x_basis = 1000
    y_basis = 1000
    z_basis = 1000

    #3 std deviations from mean - tolerance
    x_tol_u = 1000 #x tolerance, upper bound
    y_tol_u = 1000 #y tolerance, upper bound
    z_tol_u = 1000 #z tolerance, upper bound

    x_tol_l = -1000 #x tolerance, lower bound
    y_tol_l = -1000 #y tolerance, lower bound
    z_tol_l = -1000 #z tolerance, lower bound

    #number of standard deviations for toleranc\
    num_std = 3

    #bound increase to account for when there is motor motion
    m_offset = 0.1

    #values - current
    x_val = 0
    y_val = 0
    z_val = 0
    
    #interrupt counts
    int_count = 0

    #accel time keeping
    a_time = 0

    #accelertometer flag
    accel_flag = False
    
    #registers
    Out_X_LSB = 0x04 #LSB of x-axis accelerometer 
    Out_X_MSB = 0x05 #MSB of x-axis accelerometer 
    Out_Y_LSB = 0x06 #LSB of y-axis accelerometer 
    Out_Y_MSB = 0x07 #MSB of y-axis accelerometer 
    Out_Z_LSB = 0x08 #LSB of z-axis accelerometer 
    Out_Z_MSB = 0x09 #MSB of z-axis accelerometer 


    #filter stuff
    alpha = 0.2
    emay = None
    emaz = None

    old_valy = 0
    old_valz = 0

    b,a,zi = None, None, None
    c,d, yi = None,None,None



    def __init__(self):
        ...
        self.log_data = False
        self.data_log_path = "/home/camcs/rewrite_these_twinks/hardware/accel_data/accel_data_log.csv"
        self.start_time = time.time()
        self.b, self.a, self.zi = self.init_filter(cutoff=10, fs=100, order=3)
        self.d, self.c, self.yi = self.init_filter(cutoff=10, fs=100, order=3)
        # Optional: clear old data
        if os.path.exists(self.data_log_path):
            os.remove(self.data_log_path)

    def enable_logging(self, flag=True):
        self.log_data = flag
        if flag:
            print(f"Accelerometer logging enabled: {self.data_log_path}")
    
    def log_accel_data(self):
        elapsed = time.time() - self.start_time
        with open(self.data_log_path, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([elapsed, self.old_valy, self.old_valz, self.y_val, self.z_val, self.y_tol_u, self.y_tol_l, self.z_tol_u, self.z_tol_l])
    
    
    def filtery(self):
        n_val = self.y_val
        if self.emay is None:
            self.emay = n_val
        else:
            self.emay = self.alpha * n_val + (1-self.alpha)*self.emay
        return self.emay
    
    def init_filter(self,cutoff=1.5, fs=10, order=2):
        nyq = 0.5 * fs
        norm_cutoff = cutoff / nyq
        b, a = butter(order, norm_cutoff, btype='low')
        zi = lfilter_zi(b, a)  # initial state
        return b, a, zi
    
    def butter_lowpass_filter(self,data, cutoff=1.5, fs=1, order=2):
        print("butterworth")
        nyq = 0.5 * fs
        norm_cutoff = cutoff / nyq
        b, a = butter(order, norm_cutoff, btype='low')
        print("x")
        x = filtfilt(b, a, data)
        print("filt")
        return x
    
    def applyfiltery(self,new_sample):
        filtered_sample, yi = lfilter(self.d, self.c, [new_sample], zi=self.yi)
        return filtered_sample[0], yi
    
    def applyfilterz(self, new_sample):
        filtered_sample, zi = lfilter(self.b, self.a, [new_sample], zi=self.zi)
        return filtered_sample[0], zi

    def filterz(self):
        n_val = self.z_val
        if self.emaz is None:
            self.emaz = n_val
        else:
            self.emaz = self.alpha * n_val + (1-self.alpha)*self.emaz
        return self.emaz

    def compare(self, mt):
        #need to build in motion check 
        
        """ if bound_multiplier == 1:
            if not(self.y_tol_l < self.y_val < self.y_tol_u):
                self.int_count += 1 
            elif not(self.z_tol_l < self.z_val < self.z_tol_u):
                self.int_count += 1 
            else:
                self.int_count = 0 """
        

        
        
        #b, a, zi = self.init_filter(cutoff=1.5, fs=20, order=2)
        #c, d, yi = self.init_filter(cutoff=1.5, fs=20, order=2)

        y = self.y_val
        z = self.z_val
        
        # Then inside your loop or callback:
        smoothedy, self.yi = self.applyfiltery(y)
        smoothedz, self.zi = self.applyfilterz(z)
        
        
        #smoothedy = self.butter_lowpass_filter(y)
        #smoothedz = self.butter_lowpass_filter(z)


        self.old_valy = y
        self.old_valz = z
        
        self.y_val = smoothedy
        self.z_val = smoothedz

        if 3 < (time.time() - mt):
            a_inc = 0
        else:
            a_inc = 0
        
        if not(self.y_tol_l-a_inc < self.y_val < self.y_tol_u+a_inc):
            self.int_count += 1 
            self.a_time = time.time()
        elif not(self.z_tol_l-a_inc < self.z_val < self.z_tol_u+a_inc):
            self.int_count += 1 
            print("z cross")
            self.a_time = time.time()
        elif 1 < (time.time() - self.a_time):
            self.int_count = 0

        

    def convert(self,lsb,msb):
        #takes two bytes in. 16 bits, but only 12 are relevant
        #combine:
        #get rid of sign bits on msb first 
        #print("in convert", lsb, msb)
        signed = False #automatically asume false
        if msb < 16:
            #15:12 are zero (sign extended)
            big = msb* 256 #shift by 8
            signed = False #if msb_nibble < 16 - not signed 
        else:
            #15:12 are not zero (sign extened), but do not care about actual value
            h_11_8 = msb % 16 #signed - get 11 to 8 by getting remainder 

            big =  256*h_11_8 #shift by 8
            signed = True #set to true

        # LSB_b is already good
        val = lsb + big #full value 

        #for binary, the first two are 0b, then the actual binary number
        max_unsigned = 2**12 #12 bit data 
        if signed: #convert signed value
            val -= max_unsigned #signed, so need to deduct max_unsigned value 

        to_devide = 1024 #to devide: 2=2048, 1=1024, so each signed bit is 1/1024 g
        #grav = 9.81
        #val = grav*val/to_devide #convert to value based on m/s^2

        ##print(val)
        val = val/to_devide #convert to value based on g (1g = 9.81)
        return val #return converted value 


    #get basis to compare values 
    def basis(self, bus_accel): #accel is the class object
        #read data
        #start accelerometer
        
        try:
            bus_accel.write_byte_data(0x18, 0x15, 0x01) #0x15 is a config reg, 0x01 sets to active. 0x18 is accel address
        except:
            print("Basis didn't start")
        #print("get basis")
        x = [] #list to collect variable
        y = [] #list to collect variable
        z = [] #list to collect variable

        i = 0 #iteration variable 
        try:
            while i<100: #collect data till x - will take x seconds 
                #x_lsb = bus_accel.read_byte_data(accel.address, accel.Out_X_LSB) #read LSB of x-axis accelerometer 
                #x_msb = bus_accel.read_byte_data(accel.address, accel.Out_X_MSB) #read MSB of x-axis accelerometer 
                y_lsb = bus_accel.read_byte_data(self.address,  self.Out_Y_LSB) #read LSB of y-axis accelerometer 
                y_msb = bus_accel.read_byte_data(self.address,  self.Out_Y_MSB) #read MSB of y-axis accelerometer 
                z_lsb = bus_accel.read_byte_data(self.address,  self.Out_Z_LSB) #read LSB of z-axis accelerometer 
                z_msb = bus_accel.read_byte_data(self.address,  self.Out_Z_MSB) #read MSB of z-axis accelerometer 


                #print(y_lsb, y_msb)
                #print(z_lsb, z_msb)
                #x.append(convert(x_lsb,x_msb)) #convert raw value to more useable one 
                y_i = self.convert(y_lsb,y_msb)
                z_i = self.convert(z_lsb,z_msb)
                y.append(y_i) #convert raw value to more useable one 
                z.append(z_i) #convert raw value to more useable one 
                smoothedy, self.yi = self.applyfiltery(y_i)
                smoothedz, self.zi = self.applyfilterz(z_i)

                time.sleep(0.1) #sleep for one second
                i += 1 #increment 
                print("accel basis, i=", i) #let user know still going 
        except:
            print("Accel not working")

        
        #accel.x_basis = np.average(x) #average all values collected - this is basis
        self.y_basis = np.average(y) #average all values collected - this is basis
        self.z_basis = np.average(z) #average all values collected - this is basis

        #print(accel.x_basis)
        #use absolute value of mean and std dev to simplify comparisions 
        #abs(mean) + abs(2*std) < abs(value) 
        #accel.x_tol_u = abs(accel.x_basis) + abs(5*np.std(x)) #get 3 std dev of x values, upper bound 
        self.y_tol_u = (self.y_basis) + abs(self.num_std*np.std(y)) + self.m_offset #get 3 std dev of y values, upper bound. Add 0.3 for during cam movement
        self.z_tol_u = (self.z_basis) + abs(self.num_std*np.std(z)) + self.m_offset #get 3 std dev of z values, upper bound

        #accel.x_tol_l = abs(accel.x_basis) - abs(5*np.std(x)) #get 3 std dev of x values, lower bound 
        self.y_tol_l = (self.y_basis) - abs(self.num_std*np.std(y)) - self.m_offset#get 3 std dev of y values, lower bound 
        self.z_tol_l = (self.z_basis) - abs(self.num_std*np.std(z)) - self.m_offset #get 3 std dev of z values, lower bound 


    def check_accel(self, bus_accel,mt):
        #read all the values 
        try:
            #x_lsb = bus_accel.read_byte_data(accel.address, accel.Out_X_LSB)  #read LSB of x-axis accelerometer 
            #x_msb = bus_accel.read_byte_data(accel.address, accel.Out_X_MSB) #read MSB of x-axis accelerometer 
            y_lsb = bus_accel.read_byte_data(self.address, self.Out_Y_LSB) #read LSB of y-axis accelerometer 
            y_msb = bus_accel.read_byte_data(self.address, self.Out_Y_MSB) #read MSB of y-axis accelerometer 
            z_lsb = bus_accel.read_byte_data(self.address, self.Out_Z_LSB) #read LSB of z-axis accelerometer 
            z_msb = bus_accel.read_byte_data(self.address, self.Out_Z_MSB) #read MSB of z-axis accelerometer 

            
            
            #now convert, so useable 
            #accel.x_val = convert(x_lsb,x_msb) #convert value
            self.y_val = self.convert(y_lsb,y_msb) #convert value
            self.z_val = self.convert(z_lsb,z_msb) #convert value

            #print("Accel Values:", accel.y_val, accel.z_val)

            #print("Accel:", self.y_val, self.z_val)
            #now compare 
            self.compare(mt)
            

            if self.log_data:
                self.log_accel_data()
            #now see if need to set flag 
            
            if self.int_count >= 3: #changing to 1 for now to z. not using noisy x axis
                self.accel_flag = True
                print("Accelerometer motion")
                print("Accel Basis:", self.y_basis, self.z_basis)
                print("self upper tolerance:",self.y_tol_u, self.z_tol_u)
                print("Accel lower tolerance:",self.y_tol_l, self.z_tol_l)
                print("Accel values:",self.y_val, self.z_val)
                self.accel_flag_write(True)
                return True
            else:
                return False

        
        
        except:
            print("Accelerometer not working")
        


    def accel_flag_write(self,accel_int_flag):
        name = r'/home/camcs/rewrite_these_twinks/uploads/camera_motion/sensor_status.csv'
        if accel_int_flag:
            x = 1
        else:
            x = 0
        rows = [["Camera Sensor Status"], [x]]
        with open(name, 'w', newline='') as f:
            fwrite = csv.writer(f, delimiter = ',')
            for i in range(len(rows)):
                fwrite.writerow(rows[i])

