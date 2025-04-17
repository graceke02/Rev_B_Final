import time
import serial
#import matplotlib
import numpy as np
import cv2
import math

focalLength = 600

panWidth = 640
panHeight = 480

#ser = serial.Serial('/dev/ttyTHS1', 4800, timeout=1)

def getPano(angInit, angFinal, step, command_queue, response_queues, rawImage, rawLock):
    #ser.reset_input_buffer()
    #ser.reset_output_buffer()
    images = []
    angles = []
    setAngle = angInit
    
    #img = image.capture
    #images.append(img)
    
    readAngle(command_queue, response_queues)
    print(writeAngle(setAngle,command_queue, response_queues))
    print(setAngle)
    print(writeAngle(setAngle, command_queue, response_queues))
    print("x")
    time.sleep(5)
    # Get optimal new camera matrix
    
    with rawLock:
        undistorted = np.frombuffer(rawImage.get_obj(), dtype=np.uint8).reshape((480,640,3)).copy()
    
    #images.append(undistorted)
    #ser.reset_input_buffer()
    #angles.append(readAngle())
    counter = 0
    while (setAngle <= angFinal):
        setAngle += step
        print(writeAngle(setAngle, command_queue, response_queues))
        time.sleep(2)

        with rawLock:
            undistorted = np.frombuffer(rawImage.get_obj(), dtype=np.uint8).reshape((480,640,3)).copy()
            

        a = readAngle(command_queue, response_queues)

        #imaimage.capture
        images.append(undistorted)
        
        angles.append(a)
        print("took image ", counter, " at angle ", a, "\n")
        counter += 1
        

    writeAngle(0x500, command_queue, response_queues)
    #p = ser.readline()
    print("pano angles ", angles)
    return images, angles

def writeAngle(angle, command_queue, response_queues):
    command_queue.put(("pano", angle))
    while response_queues["pano"].empty():
        time.sleep(0.001)
    hexpos = response_queues["pano"].get()
    #ser.write(command.encode('utf-8'))
    return hexpos #ser.readline()
def readAngle(command_queue, response_queues):
    #global pan_position
    prefix = '0000' #prefix of what to send to motor control
    command = f"CR{prefix}\n" #full command value
    command_queue.put(("pano", command))
    while response_queues["pano"].empty():
        time.sleep(0.001)
    angle = response_queues["pano"].get()
    #ser.write(command.encode('utf-8'))
    #ser.write(command.encode('UTF-8')) #send to motor controller
    print("sent command", command)
    return angle

def pan_setup(command_queue, response_queues,rawImage, rawLock):
    print("Setup pano")
    #images, angles = getPano(400,2100,125, command_queue, response_queues,rawImage, rawLock)
    images, angles = getPano(900,1500,300, command_queue, response_queues,rawImage, rawLock)
    mingle, maxgle = 400, 0
    pixAngles=[]

    """ for i,img in enumerate(images):
        file = str(i) + "out.jpg"
        cv2.imwrite(file, img) """

    for i, img in enumerate(images):
        columnAngles=[]
        pangle = float(angles[i]*float(360/4096))
        print(pangle)
        #img = cv.imread(os.path.join(imagefolder, item))
        xlen = img.shape[1]
        centx = (xlen - 1) / 2.0
        #print(centx)
        for col in range(xlen):
            angle = math.degrees(math.atan((col - centx) / focalLength)) + pangle
            if angle < mingle:
                mingle = angle
            if angle > maxgle:
                maxgle = angle
            columnAngles.append(angle)
        pixAngles.append(columnAngles)
    print("MINGLE:", mingle, maxgle)
    columnBins = np.linspace(mingle, maxgle, panWidth + 1)

    # Initialize panorama with float32 to handle fractional weights
    panorama = np.zeros((panHeight, panWidth, 4), dtype=np.float32)

    print("About to start pano creation")
    t_pan = time.time()
    for i, img in enumerate(images):
        print("another i", i)
        #img = cv.imread(os.path.join(imagefolder, item))
        if img is None:
            continue
        img_float = img.astype(np.float32)  # Convert to float for weighting
        xlen, ylen = img.shape[1], img.shape[0]
        centx = (xlen - 1) / 2.0
        max_distance = centx

        # Calculate weights for each column (triangular weighting)
        columns = np.arange(xlen)
        distances = np.abs(columns - centx)
        weights = 1.0 - 1*(distances / max_distance)
        weights = np.clip(weights, 0.0, 1.0)  # Ensure non-negative
        #print(weights)
        bindices = np.searchsorted(columnBins, pixAngles[i], side='right') - 1
        bindices = np.clip(bindices, 0, panWidth - 1)

        #print(bindices)

        
        for col in range(xlen):
            #print(col)
            bin_idx = bindices[col]
            weight = weights[col]
            # Accumulate weighted contributions
            panorama[:, bin_idx, :3] += img_float[:, col, :] * weight
            panorama[:, bin_idx, 3] += weight

    # Normalize by the accumulated weights
    total_weights = panorama[:, :, 3]
    total_weights_safe = np.where(total_weights == 0, 1.0, total_weights)
    panorama[:, :, :3] = panorama[:, :, :3] / total_weights_safe[:, :, np.newaxis]

    # Convert to uint8 for saving/display
    panorama_rgb = np.clip(panorama[:, :, :3], 0, 255).astype(np.uint8)
    imgwidth = 640
    panfov = maxgle - mingle 
    panwidth = int((panfov/56.07)*imgwidth)
    print("time for creating pano:", time.time()-t_pan)
    #print(record.panfov)
    #print("width", record.panwidth)
    #print("fov", record.fov)
    #print("imgwidth", record.imgwidth)
    # Save the panorama
    #cv2.imshow('pano',panorama_rgb)
    cv2.imwrite('/home/camcs/rewrite_these_twinks/uploads/xypixelcolor/pano.jpg', panorama_rgb)
    #time.sleep(1)
    print("\n\nDone with Pano\n\n")
    #print(mingle,maxgle)    
    #time.sleep(5)
    #Scv2.destroyAllWindows()
    
    #save a nnumpy file with mingle and maxgle values 
    pangles = np.array([mingle,maxgle])
    np.save("pangles.npy",pangles)


