import cv2
import numpy as np
import time

def img_cap(img_array,rawLock):
    #this will always be on so no delay in getting frames 

    print("image capture process begun")
    camera_matrix = np.load("/home/camcs/rewrite_these_twinks/cam_functions/camera_matrix.npy")
    dist_coeffs = np.load("/home/camcs/rewrite_these_twinks/cam_functions/dist_coeff.npy")


    h, w = 1080,1920
    new_camera_matrix, roi = cv2.getOptimalNewCameraMatrix(camera_matrix, dist_coeffs, (w, h), 0.75, (w, h))

    map1, map2 = cv2.initUndistortRectifyMap(camera_matrix, dist_coeffs, None, new_camera_matrix, (1920, 1080), cv2.CV_32FC1)

    cap = cv2.VideoCapture(0, cv2.CAP_V4L2) #initialize camera

    # Set MJPEG first to reduce CPU load
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    cap.set(cv2.CAP_PROP_FPS, 30)
    cap.set(cv2.CAP_PROP_BUFFERSIZE,1)
    
    while True:
        s = time.time()
        ret, frame = cap.read()
        while not(ret): #not recording properly 
            time.sleep(0.5)
            ret, frame = cap.read()
            if (time.time()-s) > 8:
                print("Can't receive frame (stream end?). Exiting ...") #let user know
                break

        #undistorted = cv2.undistort(frame, camera_matrix, dist_coeffs, None, new_camera_matrix)
        undistorted = cv2.remap(frame, map1, map2, interpolation=cv2.INTER_LINEAR)
        #height,width = frame.shape[:2]
        # Crop to ROI
        x, y, w, h = roi
        undistorted = undistorted[y:y+h, x:x+w]
        undistorted = undistorted[:480, :640]
        undistorted = cv2.flip(undistorted, -1)

        with rawLock:
            #print("imcap: writing raw frame to first buffer")
            # Create a NumPy view over the shared memory buffer and reshape it to the frame dimensions.
            np_frame = np.frombuffer(img_array.get_obj(), dtype=np.uint8).reshape((480, 640, 3))
            np.copyto(np_frame, undistorted)  # Copy the entire frame at once
        
        #cv2.waitKey(1)
    cap.release()
