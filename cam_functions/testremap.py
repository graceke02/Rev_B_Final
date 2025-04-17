import cv2
import time
import numpy as np # Needed for camera matrices and loading files
import os # Needed for checking file existence

# --- Configuration ---
CAMERA_INDEX = 0  # Usually 0 for built-in webcam, adjust if needed
CALIBRATION_FILE_CAM = "camera_matrix.npy"
CALIBRATION_FILE_DIST = "dist_coeff.npy"
# Requested Camera Settings
REQ_WIDTH = 1920
REQ_HEIGHT = 1080
REQ_FPS = 30

# --- Main Execution ---
if __name__ == "__main__":
    print("Single-process capture and GPU undistortion starting...")

    # --- Load Camera Calibration ---
    if not os.path.exists(CALIBRATION_FILE_CAM) or not os.path.exists(CALIBRATION_FILE_DIST):
         print("------------------------------------------------------")
         print(f"Error: Calibration file(s) not found.")
         print(f"       Expected '{CALIBRATION_FILE_CAM}' and '{CALIBRATION_FILE_DIST}'")
         print("       in the same directory as the script.")
         print("       Cannot proceed without calibration data.")
         print("------------------------------------------------------")
         exit()

    try:
        print(f"Loading camera matrix from: {CALIBRATION_FILE_CAM}")
        camera_matrix = np.load(CALIBRATION_FILE_CAM).astype(np.float32) # Ensure float32 type
        print(f"Loading distortion coefficients from: {CALIBRATION_FILE_DIST}")
        dist_coeffs = np.load(CALIBRATION_FILE_DIST).astype(np.float32) # Ensure float32 type
        print(f"Loaded dist_coeffs raw data: {dist_coeffs}") # Print raw loaded data
        print(f"Loaded dist_coeffs raw shape: {dist_coeffs.shape}")

        # --- Fix: Reshape dist_coeffs if it's 2D (e.g., shape (1, N)) ---
        if dist_coeffs.ndim == 2 and dist_coeffs.shape[0] == 1:
            print(f"Reshaping dist_coeffs from {dist_coeffs.shape} to 1D array...")
            dist_coeffs = dist_coeffs.flatten() # Convert [[a,b,c]] to [a,b,c]
            print(f"Reshaped dist_coeffs shape: {dist_coeffs.shape}")
        # --- End Fix ---

        print("Calibration files loaded successfully.")

        # --- Basic Validation of Loaded Data ---
        valid_calibration = True
        if camera_matrix.shape != (3, 3):
            print(f"Error: Loaded camera matrix has incorrect shape {camera_matrix.shape}. Expected (3, 3).")
            valid_calibration = False
        # Expecting a 1D array for distortion coefficients (e.g., (5,), (8,), (12,), (14,))
        # This check now runs *after* the potential reshape
        if dist_coeffs.ndim != 1 or dist_coeffs.shape[0] < 4:
             print(f"Error: Loaded distortion coefficients have incorrect shape {dist_coeffs.shape} after potential reshape. Expected a 1D array (e.g., (5,) or more).")
             valid_calibration = False

        if not valid_calibration:
            print("Calibration data validation failed. Exiting.")
            exit()

    except Exception as e:
        print(f"Error reading calibration files: {e}")
        exit()


    # --- Check for CUDA ---
    if cv2.cuda.getCudaEnabledDeviceCount() == 0:
        print("------------------------------------------------------")
        print("Error: No CUDA-enabled GPU found OR")
        print("       OpenCV was not built with CUDA support.")
        print("       Cannot perform GPU undistortion.")
        print("------------------------------------------------------")
        exit()
    print(f"Found {cv2.cuda.getCudaEnabledDeviceCount()} CUDA device(s).")
    print(f"Using CUDA device: {cv2.cuda.getDevice()}")

    # --- Camera Initialization ---
    print(f"Attempting to open camera {CAMERA_INDEX} using V4L2 backend...")
    # Use V4L2 backend explicitly, common on Linux/Jetson
    cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_V4L2)

    # Check if camera opened initially
    if not cap.isOpened():
        print(f"Error: Could not open video device {CAMERA_INDEX} using V4L2 backend.")
        exit()
    print("Camera opened successfully. Setting properties...")

    # --- Set Camera Properties ---
    # Set MJPEG first to potentially reduce CPU load during capture
    print(f"Requesting FourCC: MJPG")
    if not cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG')):
        print("Warning: Failed to set FourCC to MJPG.")

    print(f"Requesting Frame Width: {REQ_WIDTH}")
    if not cap.set(cv2.CAP_PROP_FRAME_WIDTH, REQ_WIDTH):
         print(f"Warning: Failed to set Frame Width to {REQ_WIDTH}.")

    print(f"Requesting Frame Height: {REQ_HEIGHT}")
    if not cap.set(cv2.CAP_PROP_FRAME_HEIGHT, REQ_HEIGHT):
         print(f"Warning: Failed to set Frame Height to {REQ_HEIGHT}.")

    print(f"Requesting FPS: {REQ_FPS}")
    if not cap.set(cv2.CAP_PROP_FPS, REQ_FPS):
         print(f"Warning: Failed to set FPS to {REQ_FPS}.")

    # Buffer size 1 tries to grab the most recent frame, potentially dropping older ones
    # May reduce latency but can lead to dropped frames if processing is slow
    print("Requesting Buffer Size: 1")
    if not cap.set(cv2.CAP_PROP_BUFFERSIZE, 1):
        print("Warning: Failed to set Buffer Size to 1.")

    # --- Verify Settings (Optional but recommended) ---
    # Check what the camera actually reports after setting properties
    actual_fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
    # Decode FourCC integer back into characters
    actual_fourcc_str = "".join([chr((actual_fourcc >> 8 * i) & 0xFF) for i in range(4)])
    actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    actual_fps = cap.get(cv2.CAP_PROP_FPS)
    actual_buffer = int(cap.get(cv2.CAP_PROP_BUFFERSIZE))
    print(f"--- Verified Camera Settings ---")
    print(f"  FourCC: {actual_fourcc_str}")
    print(f"  Width:  {actual_width}")
    print(f"  Height: {actual_height}")
    print(f"  FPS:    {actual_fps}")
    print(f"  Buffer: {actual_buffer}")
    print(f"------------------------------")


    # Final check if camera is still open after setting properties
    if not cap.isOpened():
        print(f"Error: Camera device {CAMERA_INDEX} closed unexpectedly after setting properties.")
        exit()

    # --- Get Frame Dimensions (use actual reported dimensions now) ---
    frame_width = actual_width
    frame_height = actual_height
    # Read one frame to ensure capture works with settings and get frame object
    ret, frame = cap.read()
    if not ret or frame is None:
        print(f"Error: Could not read initial frame after setting camera properties.")
        cap.release()
        exit()
    print(f"Successfully read initial frame with actual dimensions: {frame_width}x{frame_height}")


    # --- Calculate Undistortion Maps (on CPU) ---
    print("Calculating undistortion maps...")
    h, w = frame_height, frame_width # Use actual height/width
    alpha = 0 # Adjust alpha (0=crop, 1=keep all pixels) as needed
    new_camera_matrix, roi = cv2.getOptimalNewCameraMatrix(camera_matrix, dist_coeffs, (w, h), alpha, (w, h))
    print(f"Calculated ROI: {roi}") # Print ROI for debugging

    if roi == (0,0,0,0):
        print("Warning: Region of Interest (ROI) after undistortion is empty. Check calibration or alpha value.")
        print("         Undistorted frames might be empty.")

    map1, map2 = cv2.initUndistortRectifyMap(camera_matrix, dist_coeffs, None, new_camera_matrix, (w, h), cv2.CV_32FC1)
    print("Maps calculated.")

    # --- Upload Maps to GPU ---
    print("Uploading maps to GPU...")
    gpu_map1 = cv2.cuda_GpuMat()
    gpu_map2 = cv2.cuda_GpuMat()
    gpu_map1.upload(map1)
    gpu_map2.upload(map2)
    print("Maps uploaded.")

    # --- Create GPU Mats (Initialize empty) ---
    gpu_frame = cv2.cuda_GpuMat()
    # Initialize as empty; remap will allocate it with the correct size/type
    gpu_undistorted_frame = cv2.cuda_GpuMat()
    print("GPU Mats initialized.")

    # --- Create Display Windows ---
    window_name_orig = "Original Stream"
    window_name_undistorted = "Undistorted Stream (GPU)"
    #cv2.namedWindow(window_name_orig, cv2.WINDOW_NORMAL)
    cv2.namedWindow(window_name_undistorted, cv2.WINDOW_NORMAL)

    frame_count = 0
    start_time = time.time()

    try:
        # Process the first frame read earlier
        gpu_frame.upload(frame)
        # Perform GPU remapping; dst will be allocated/resized by remap
        cv2.cuda.remap(gpu_frame, gpu_map1, gpu_map2, interpolation=cv2.INTER_LINEAR, dst=gpu_undistorted_frame)
        undistorted_frame = gpu_undistorted_frame.download()

        # --- Display original frame ---
        #cv2.imshow(window_name_orig, frame)

        # --- Check and display undistorted frame ---
        if undistorted_frame is not None and undistorted_frame.shape[0] > 0 and undistorted_frame.shape[1] > 0:
            cv2.imshow(window_name_undistorted, undistorted_frame)
        else:
            # Create a black placeholder if the undistorted frame is empty/invalid
            black_placeholder = np.zeros((frame_height, frame_width, 3), dtype=np.uint8)
            cv2.imshow(window_name_undistorted, black_placeholder)
            print("Warning: Undistorted frame is empty or invalid after download (initial frame). Displaying black.")
        # --- End Check ---

        frame_count += 1

        # --- Main Loop ---
        while True:
            ret, frame = cap.read()
            if not ret:
                # Attempt to read again immediately if buffer might be involved
                # print("Retrying frame grab...")
                # time.sleep(0.001) # Small delay before retry
                # ret, frame = cap.read()
                # if not ret:
                    print("Failed to grab frame, stopping.")
                    break # Exit loop if frame reading fails consistently

            # Ensure frame is not None even if ret is True (can happen sometimes)
            if frame is None:
                print("Warning: Grabbed frame is None, skipping iteration.")
                time.sleep(0.01) # Wait a bit longer if frames are None
                continue

            gpu_frame.upload(frame)
            gpu_undistorted_frame = cv2.cuda.remap(gpu_frame, gpu_map1, gpu_map2,
                                                interpolation=cv2.INTER_LINEAR)
            undistorted_frame = gpu_undistorted_frame.download()
            undistorted_frame = cv2.flip(undistorted_frame, -1)
            print(undistorted_frame.shape)
            undistorted_frame = undistorted_frame[:480, :640]

            # --- Display original frame ---
            #cv2.imshow(window_name_orig, frame)

            # --- Check and display undistorted frame ---
            if undistorted_frame is not None and undistorted_frame.shape[0] > 0 and undistorted_frame.shape[1] > 0:
                cv2.imshow(window_name_undistorted, undistorted_frame)
            else:
                # Use the same placeholder logic as above if needed
                black_placeholder = np.zeros((frame_height, frame_width, 3), dtype=np.uint8)
                cv2.imshow(window_name_undistorted, black_placeholder)
                print("Warning: Undistorted frame is empty or invalid after download (loop frame). Displaying black.")
             # --- End Check ---

            frame_count += 1

            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("Quit key pressed, stopping.")
                break

    except KeyboardInterrupt:
        print("Process interrupted by Ctrl+C.")
    except cv2.error as e:
        # Catch potential errors during processing as well
        print(f"OpenCV Error during processing: {e}")
        # Decide if you want to continue or break on error
        # break
    finally:
        # --- Cleanup ---
        end_time = time.time()
        print("Shutting down...")
        cap.release()
        cv2.destroyAllWindows()

        # --- Performance Metrics ---
        elapsed_time = end_time - start_time
        if elapsed_time > 0 and frame_count > 0:
            fps = frame_count / elapsed_time
            print(f"Processed {frame_count} frames in {elapsed_time:.2f} seconds.")
            print(f"Average FPS: {fps:.2f}")
        else:
            print(f"Processed {frame_count} frames.")
            print("Not enough time elapsed or frames processed for FPS calculation.")

    print("Process finished.")
