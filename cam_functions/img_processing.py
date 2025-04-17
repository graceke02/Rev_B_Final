import cv2
import numpy as np 
import csv 
import time


def img_processing(img_array, flask_array,output_name,img_processing_event,processed_lock, rawLock,response_queues, command_queue):

    print("entering img processing")
    rows = []

    file_name = r'/home/camcs/rewrite_these_twinks/uploads/xypixelcolor/PropertyLineSetupXYPixelColorFile.csv'

    with open(file_name, newline = '') as f:
        fread = csv.reader(f)
        for row in fread:
            rows.append(row)              

    p = []
    #print(len(rows), len(row))
    #print(rows[0][0])
    for i in range(1,len(rows)):
        #####FOR NOW ONLY TESTING, SO 
        #CHECK HEADERS TO GET CORRECT DATA
        if rows[0][0] == 'X Values' and rows[0][1] == 'Y Values':
            p.append(rows[i])
    
    #print(rows)
    
    points = np.array(p, dtype = np.int32)
    points = points.reshape((-1,1,2)) #reshape format

    #get numpy array
    pangles = np.load("pangles.npy")
    print("pangles = ", pangles)
    mingle = pangles[0]
    maxgle=pangles[1]
    anglePerCol = 0.1
    maskWidth = (maxgle-mingle)/anglePerCol #create mask with constant angle per column
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    fps = 30
    width = 640
    height = 480

    out = cv2.VideoWriter(output_name, fourcc, fps, (width, height))


    mask = np.zeros((height,width), dtype=np.uint8) #set up so cv2 can use
    cv2.fillPoly(mask, [points], (255,255,255)) #make a filled polygon

    maskbigly = cv2.resize(mask, (int(maskWidth),480), interpolation = cv2.INTER_NEAREST)
    #add 500 pixels of blocking on each side
    maskbigly = cv2.copyMakeBorder(maskbigly, 0,0,500,500,cv2.BORDER_CONSTANT, value=[0,0,0])
    #create list of angles that each column in mask bigly corresponds to
    #start at mingle, subtract the angles of the border, then add angle per column
    maskAngles = mingle - (500*anglePerCol) + np.arange(maskbigly.shape[1])*anglePerCol #create list of angle in degrees for each column in mask
    
    #print("mask angle:", maskAngles)
    
    pixAngleOffsets = np.arange(-320, 320,1) #evey pixel offset
    pixAngleOffsets = np.arctan(pixAngleOffsets/600) #find angle from center
    pixAngleOffsets = np.degrees(pixAngleOffsets) #convert to degrees

    #print("pixAngles:", pixAngleOffsets)

    #empty response queue and put command in to set buffer of 1 
    while not response_queues['img_blocking'].empty():
        response_queues['img_blocking'].get()

    command_queue.put(('img_blocking', f"CR0000\n"))
    while response_queues["img_blocking"].empty():
        time.sleep(0.001)
    newhexpos = response_queues['img_blocking'].get()
    newnewhexpos = newhexpos


    while img_processing_event.is_set():
        with rawLock:
            #print("improc: reading raw frame from first buffer")
            frame = np.frombuffer(img_array.get_obj(), dtype=np.uint8).reshape((480,640,3)).copy()

        command_queue.put(('img_blocking', f"CR0000\n"))
        hexpos = newhexpos
        newhexpos = newnewhexpos

        while response_queues["img_blocking"].empty():
            time.sleep(0.001)

        #hexpos = newhexpos
        newnewhexpos = response_queues["img_blocking"].get()

        
        if (hexpos > 0xc00):
            hexpos -= 4096
        centerAngle = 360*float(hexpos) / 4096
        
        imageAngles = pixAngleOffsets + centerAngle #find absolute angle of each column
        #print("image angles: \n", imageAngles.size, imageAngles)
        angleDiffs = np.abs(imageAngles[:, np.newaxis]-maskAngles)
        #print("angleDiffs: \n", angleDiffs.size, angleDiffs)
        closestColumn = np.argmin(angleDiffs, axis=1)
        #print("closestColumn: \n", closestColumn.size, closestColumn)
        maskSlice = maskbigly[:, closestColumn]
        #print("maskSlice: \n", maskSlice.size, maskSlice)
        maskSlice = cv2.cvtColor(maskSlice, cv2.COLOR_GRAY2BGR)

        inverted = cv2.bitwise_and(frame, maskSlice)

        with processed_lock:
            #print("improc: writing processed frame to second buffer")
            # Create a NumPy view over the shared memory buffer and reshape it to the frame dimensions.
            np_frame = np.frombuffer(flask_array.get_obj(), dtype=np.uint8).reshape((480, 640, 3))
            np.copyto(np_frame, inverted)  # Copy the entire frame at once
        #cv2.imshow('frame', inverted) #show in window the frame
        out.write(inverted) #write to file
    
    #end of recordiung
    out.release()
    #ai_video_queue.put(output_name)

        