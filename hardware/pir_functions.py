import cv2
import numpy as np
import time
from smbus2 import SMBus
import datetime
import serial
import csv


class PIR():
    pir1_motion_time = 0
    pir2_motion_time = 0
    pir3_motion_time = 0
    motion_time = 0

    pir1_flag = False
    pir2_flag = False
    pir3_flag = False

    def read(self, bus_pir):
        pir1 = 0x50
        pir2 = 0x55
        pir3 = 0x54


        try: #see if can read motion
            #write 0 to them
            
            ADC_out1 =  bus_pir.read_i2c_block_data(pir1, 0x00, 2) #0x00 is the data reg. Read two bytes
            ADC_out2 =  bus_pir.read_i2c_block_data(pir2, 0x00, 2)
            ADC_out3 =  bus_pir.read_i2c_block_data(pir3, 0x00, 2)
            #output is a list with two data points 

            #ADC_out 0 is MSB of data. ADC_out 2 contains lsb 
            #Output is odd - 0x0'value'0. First and last 4 bits are reserved values
            #Value is actually only 8 bits
            #MSB nibble - need to bitshift left by 4
            #LSB nibble - need to bitshift right by 4
            data1 = ADC_out1[0]*16 + ADC_out1[1]/16 #transform, PIR1
            data2 = ADC_out2[0]*16 + ADC_out2[1]/16 #transform, PIR2
            data3 = ADC_out3[0]*16 + ADC_out3[1]/16 #transform, PIR3

            #0xFFF = 3.3V (ref voltage)
            #motion_threshold = 148 #1.9V - ADC value. val = (1.9/3.3)*256
            motion_threshold = 110
            #motion_ended_threshold = 0.5 #so this value is kind of unknown - but from observing this is good
            motion_ended_threshold = 39 #0.5V - ACD value. val = (0.5/3.3)*256
            
            
            #add logic to make motor movement smoother. Analog volotage fluctuates wildly, so with out logic motor movement is erratic 
            
            #now compare 
            if (data1 >  motion_threshold) or (data1 <  motion_ended_threshold): #over/unter threshold actively
                self.pir1_flag = True
                self.pir1_motion_time = time.time()
                #need to clear any alert regs now. Alert only goes to zero when a 1 is written to flag
                bus_pir.write_byte_data(0x50,0x01, 0x03)
            elif (time.time() -  self.pir1_motion_time) < 0.3: #logic to reduce changes/spiking in behairo.
                self.pir1_flag = True
            else:
                self.pir1_flag = False
            
            if (data2 > motion_threshold) or (data2 <  motion_ended_threshold): #actively high/low
                self.pir2_flag = True
                self.pir2_motion_time = time.time()
                bus_pir.write_byte_data(0x54,0x01, 0x03) #clear alert reg
            elif (time.time() -  self.pir2_motion_time) < 0.3:  #logic to reduce changes/spiking in behairo.
                self.pir2_flag = True
            else:
                self.pir2_flag = False
            
            if (data3 > motion_threshold) or (data3 <  motion_ended_threshold): #actively high/low
                self.pir3_flag = True
                self.pir3_motion_time = time.time()
                bus_pir.write_byte_data(0x55,0x01, 0x03) #clear alert reg
            elif (time.time() -  self.pir3_motion_time) < 0.3:  #logic to reduce changes/spiking in behaior
                self.pir3_flag = True
            else:
                self.pir3_flag = False

            
            #set overall pir flags 
            if  self.pir1_flag or  self.pir2_flag or  self.pir3_flag:
                self.motion_time = time.time()


            bus_pir.write_byte_data(0x50, 0x01, 0x03)  #clear alert register
            bus_pir.write_byte_data(0x54, 0x01, 0x03)  #clear alert register
            bus_pir.write_byte_data(0x55, 0x01, 0x03)  #clear alert register
        
            
            return self.pir1_flag, self.pir2_flag, self.pir3_flag, self.motion_time

        except IOError: #not reading PIR correctly 
            print("Error reading form PIRs") #let user know
            return 0,0,0

    
    def pan_to_sensor(self):
        #logic - determine where to move 
        #62 degree FOV - seperate 180 based on this
        #180/62 = 2.9, so 3 positions will position it so those three have no overlap
        #5 positions will all for greater overlap 

        #1000 is pir1 (right) 
        #750 is pir2 (middle)
        #500 is pir3 (left)

        #first check if all three are triggered
        if self.pir1_flag and self.pir2_flag and self.pir3_flag:
            #pan_val = pan_position #if all three are triggered - don't move 
            #print("do nothing")
            p = False
        
        
        #have checked if all 3 are triggered - then 
        #only need to check two (no not(pirx)), as know 3 are not triggered
        #check is 1 and 2 are on
        elif self.pir1_flag and self.pir2_flag:
            #pan_val = 0x200 #in between 1 and 2
            pan_val = 1450#1625
            p = True
        elif self.pir3_flag and self.pir2_flag:
            pan_val = 800 #in between 3 and 2
            p = True
        elif self.pir1_flag and self.pir3_flag:
            #pan_val = pan_position #triggered at 1 and 3 - 
            p = False
            #no way to see both, so for now just stay 
        #motion has been triggered - but now know only 1 has been triggered
        #check each individually
        elif self.pir1_flag:
            pan_val = 1750 #only 1 triggered
            p = True
        elif self.pir2_flag:
            pan_val = 1150 #only 1 triggered
            p = True
        elif self.pir3_flag:
            pan_val = 500 #only 1 triggered
            p = True
        else:
            p = False


        #IF POSITION IS ALREADY SET TO WHAT WE WANT - DONT SEND A NEW COMMAND
        if p:# and (set_and_status.position != pan_val):
            #command_queue.put(pan_val)
            return pan_val
            """ hex_value = f"{pan_val:03X}"[-3:] #hex val of pan 
            prefix = '0' #prefix of what to send to motor control
            command = f"CO{prefix}{hex_value}\n" #full command value
            command_queue.put(('motion_detection', command))

            set_and_status.position = pan_val """
        else:
            return None
            #command_queue.put(0)


        



