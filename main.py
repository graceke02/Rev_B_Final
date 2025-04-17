import numpy as np
import time
from smbus2 import SMBus
import datetime
import multiprocessing
from flask import Flask
import threading
import Jetson.GPIO as GPIO
import serial 
import ctypes



import sys
sys.path.append(r'/home/camcs/rewrite_these_twinks/Facial_Detection_Model5')
sys.path.append(r'/home/camcs/rewrite_these_twinks/hardware')
sys.path.append(r'/home/camcs/rewrite_these_twinks/cam_functions')
from cam_functions.img_capture import img_cap

#from Facial_Detection_Model5.Model_with_jetson import model_with_jetson_main

from flask_Server import app
from cam_functions.img_processing import img_processing

from flask_Server import run_flask

from auto_delete import del_videos
from hardware.hardware_manager import hardware_handler

GPIO.cleanup()


def run_auto_delete(config):
    del_time = config['auto_del_time']
    del_videos(del_time)
    t = 24 * 60 * 60
    time.sleep(t)


def set_name(): #this sets up recording name 
    x = str(datetime.datetime.now())
    s = x.split(" ")
    date = s[0].split('-')
    time_h = s[1].split(":")
    sec = time_h[2].split(".")
    l = date[1] + date[2] + date[0] + ' ' + time_h[0] +time_h[1] + sec[0] + '.mp4'
    #self.output_name = r'/home/camcs/uploads/videos/' + repr(l)[1:-1]
    output_name = r'/home/camcs/rewrite_these_twinks/uploads/raw_videos/' + repr(l)[1:-1]
    return output_name


def recording_logic(gpio_flags,gpio_lock, img_processing_event, output_name_queue,live_streaming, live_lock,config_lock):#, recording_name_queue):
    #gpio_flags = {"pir1_flag" : False, "pir2_flag":False, "pir3_flag":False, "pir_time":0, "accel_flag":False}

    print("Start recording stuff")
    while True:
        with gpio_lock:
            a_flag = gpio_flags['accel_flag']
        with config_lock:
            c_flag = config["correct_prop_lines"] and config["cam_on"]
        
        if a_flag or not(c_flag): #check for tampering and that new property lines have been uploaded 
            img_processing_event.clear() #stop any image processing 
            time.sleep(0.1)
            #print("bad")
            continue

        #now we are going to check for motion or live streaming
        with gpio_lock:
            motion_t = gpio_flags["pir_time"]
            motion = (gpio_flags["pir1_flag"] or gpio_flags["pir2_flag"] or gpio_flags["pir3_flag"]) or (10  > (time.time() - motion_t))
            

        with live_lock:
            live_stream = live_streaming.value
        
        #print("Motion is true?", motion)
        #print("IS img event set?", img_processing_event.is_set())

        if not(img_processing_event.is_set()) and (motion or live_stream): #want to video - just starting 
            print("Start video")
            recording_name = set_name() #get recording name
            print("\n\nRecording Name:\n", recording_name, "\n\n")
            output_name_queue.put(recording_name) #put name in queue
            img_processing_event.set() #set processing event - processing only happens while this is set
        elif (10  > (time.time() - motion_t)) or live_stream: #in live stream or not 10 seconds from last motion detection 
            time.sleep(0.01)
            continue #keep going
        #elif (img_processing_event.is_set()) and (10  < (time.time() - gpio_flags["motion_time"])) and not(live_stream):
        else:
            img_processing_event.clear() #turn this off 
            #print("Done recording")
        
        time.sleep(0.1)
    



def ai_event_loop(ai_video_queue):
    while True:
        #ai_loop_event.wait()
        #print("start ai loop")
        #ai_fake_funciton()
        if not(ai_video_queue.empty()):
            video_path = ai_video_queue.get()
            time.sleep(1)
            #print("sent",record.output_name)
            #ai_loop_event.clear() 
            #model_with_jetson_main(video_path)

        #ai_loop_event.clear()
        time.sleep(0.1)


def img_loo_process(rawImage, processedImage,output_name_queue,img_processing_event,processed_lock, rawLock, ai_video_queue, response_queues, command_queue):#output_name, cam_event):
    print("Start cam img")
    while True:
        #cam_img_event.wait()
        #img_processing_event.wait()
        while output_name_queue.empty():
            time.sleep(0.01)
        
        o_name = output_name_queue.get()

        print("\n\n\n\n\START AJDJSJFJJJFDJJSDAJFJD\n\n\n\n")
        #time.sleep(1)
        img_processing(rawImage, processedImage,o_name,img_processing_event,processed_lock, rawLock, response_queues, command_queue)#output_name, cam_event)

        ai_video_queue.put(o_name)

def serial_process(command_queue, response_queues,move_time_queue):#command_queue, response_queues):
    #this process accepts tuple inputs from command queue
    #process name, command packet
    #then sends the command packet over serial and returns to the appropriate response queue

    ser = serial.Serial('/dev/ttyTHS1', 38400, timeout=1)
    
    desired_pos = 1000 #desired position is the one set by a move command 

    print("Serial worker began")
    while True:
        # Expecting a tuple: (process_id, command)
        while command_queue.empty():
            time.sleep(0.0005)

        process_id, command = command_queue.get()
        #print("recieved from ", process_id, " with command ", command)
        
        if command == "CR0000\n":
            set_pos = False
        elif process_id == 'app_movement':
            if command == 'right':
                pos = desired_pos +150
            else:
                pos = desired_pos-150
            set_pos = True

            if pos < 450:
                pos = 450
            elif pos > 1850:
                pos = 1850
        
        elif (process_id == 'motion_detection') or (process_id == 'pano'):
            #need to check in settings if camera motion is allowed 
            pos = command
            set_pos = True
        else:
            set_pos = False


        if set_pos:
            t = time.time()
            move_time_queue.put(t)
            hex_value = f"{pos:03X}"[-3:] #hex val of pan 
            command = f"CO0{hex_value}\n" #full command value
            desired_pos = pos

        
        # Send the command over serial
        #print("sent command ",command)
        ser.write(command.encode('UTF-8'))
        response = ser.readline()
        #print("received response ", response)
        hexpos= int(response.strip(), 16)

        # Put the response into the corresponding response queue.
        #if process_id == 'img_blocking' :
        response_queues[process_id].put(hexpos)
        
        time.sleep(0.001) #let other stuff run on core



if __name__ == '__main__':

    #get accurate position 
     with multiprocessing.Manager() as manager:
        config = manager.dict({"auto_del_time":40, "motion_allowed":True, "cam_on":True, "correct_prop_lines":False}) #correct property lines are so we don't record until there are correct lines
        config_lock = multiprocessing.Lock()
        gpio_flags = manager.dict({"pir1_flag" : False, "pir2_flag":False, "pir3_flag":False, "pir_time":0, "accel_flag":True}) #accel flag is true at beginning - have not taken basis yet 
        batt_symbol = multiprocessing.Value('i',0)
        output_name = multiprocessing.Queue()
        command_queue = multiprocessing.Queue()
        img_processing_event = multiprocessing.Event()
        ai_video_queue = multiprocessing.Queue()
        basis_queue = multiprocessing.Queue()
        gpio_lock = multiprocessing.Lock()
        move_time_queue = multiprocessing.Queue()

        live_streaming = multiprocessing.Value(ctypes.c_bool, False)
        live_lock = multiprocessing.Lock()

        response_queues = {
            'img_blocking': multiprocessing.Queue(),
            'pano': multiprocessing.Queue(),
            'motion_detection' : multiprocessing.Queue(),
            'app_movement' : multiprocessing.Queue(), 
            'app_pan' : multiprocessing.Queue()
        }
        
        print("start threading")

        serial_worker = multiprocessing.Process(target=serial_process, args = (command_queue, response_queues,move_time_queue,)) #process for serial 
        serial_worker.start() #start serial - infinite loop

        hardWareProcess = multiprocessing.Process(target = hardware_handler,
            args=(gpio_flags, batt_symbol, gpio_lock, command_queue, basis_queue, config, config_lock,move_time_queue))
        hardWareProcess.daemon = True
        hardWareProcess.start()
        
        rawImage = multiprocessing.Array('B', 480*640*3)
        rawImageLock = multiprocessing.Lock()

        processed_image = multiprocessing.Array('B', 480*640*3)
        processed_lock = multiprocessing.Lock()
        
        image_capture_process = multiprocessing.Process(target = img_cap, args=(rawImage, rawImageLock,))
        image_capture_process.daemon = True
        image_capture_process.start()

        #recording_logic(gpio_flags, live_stream, img_processing_event, output_name_queue,live_streaming, live_lock,):
        image_processing_process = multiprocessing.Process(target = img_loo_process,
            args=(rawImage, processed_image,output_name,img_processing_event,processed_lock,rawImageLock,ai_video_queue,response_queues, command_queue))
        image_processing_process.daemon = True
        image_processing_process.start()
        
        ai_thread = threading.Thread(target=ai_event_loop, args=(ai_video_queue,)) #ai processing loop
        #ai_thread = multiprocessing.Process(target=ai_event_loop)
        ai_thread.daemon = True #don't end program if this ends
        ai_thread.start() #start - infinite loop

        rec_logic_process = multiprocessing.Process(target = recording_logic, args=(gpio_flags, gpio_lock, img_processing_event, output_name,live_streaming, live_lock,config_lock))
        rec_logic_process.daemon = True
        rec_logic_process.start()


        # Run Flask in the main thread
        flask_process = multiprocessing.Process(target=run_flask,
            args=(processed_image, processed_lock, batt_symbol, command_queue, basis_queue, config, config_lock, live_streaming, live_lock,rawImage, rawImageLock,response_queues,img_processing_event,))
        flask_process.start()

        serial_worker.join()
        hardWareProcess.join()
        image_capture_process.join()
        image_processing_process.join()
        rec_logic_process.join()
        flask_process.join()

        GPIO.cleanup()
