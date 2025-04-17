from ultralytics import YOLO
import os 
import csv 
import cv2
import time
yolo_model = YOLO("yolo11n.pt")  # YOLOv8 nano for human detection

time.sleep(20)

#USER_FOLDER = r'/home/camcs/rewrite_these_twinks/uploads/users'
#OUTPUT_VIDEO_FOLDER = r'/home/camcs/rewrite_these_twinks/uploads/videos' 
INPUT_VIDEO_FOLDER = '/rewrite_these_twinks/uploads/if_videos'
OUTPUT_VIDEO_FOLDER = r'/rewrite_these_twinks/uploads/videos' 
EXCEL_SHEET_PATH = os.path.join(OUTPUT_VIDEO_FOLDER, 'RecordedVideoNames.csv') #update this to the video_sheet in videos folder

recorded_video_names = []

human_box_excel = r'/rewrite_these_twinks/uploads/if_videos/bounding_boxes.csv' 

bounding_box = []

def get_all_recorded_video_names():
    for filename in os.listdir(OUTPUT_VIDEO_FOLDER): #look at output video folder to get names of all post-processed videos
        if filename == 'RecordedVideoNames.csv':
                continue
        if filename == 'bounding_boxes.csv':
            continue
        recorded_video_names.append(filename)


def troll_for_videos():
    while True:
        for filename in os.listdir(INPUT_VIDEO_FOLDER):
            if not (filename.startswith("0") or filename.startswith("1")):
                time.sleep(1)
                continue

            if filename in recorded_video_names:
                continue
            
            file_path = os.path.join(INPUT_VIDEO_FOLDER, filename)
            
            if os.path.getsize(file_path) < 1024:
                continue

            
            # Wait for file to stabilize
            if time.time() - os.path.getmtime(file_path) < 5:
                continue

            print(f"Processing: {filename}")
            process_video(file_path)
            recorded_video_names.append(filename)
        
        time.sleep(1)

         


def process_video(input_path):
    video_capture = cv2.VideoCapture(input_path)
    if not(video_capture.isOpened()):
        print("faild to open")
        return
    frame_width = int(video_capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(video_capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = int(video_capture.get(cv2.CAP_PROP_FPS))
    print("FPS:", fps)

    resize_width = 640
    resize_height = 480

    # Extract the original video name (without extension)
    original_video_name = os.path.splitext(os.path.basename(input_path))[0]

    unknown_detected = False

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    output_filename = f"temp_{original_video_name}.mp4"
    output_path = os.path.join(OUTPUT_VIDEO_FOLDER, output_filename)
    out = cv2.VideoWriter(output_path, fourcc, 5, (resize_width, resize_height))
    
    frame_count = 0

    while True:
        ret, frame = video_capture.read()
        if not ret:
            print("Finished processing video.")
            break

        #frame = cv2.resize(frame, (resize_width, resize_height))

        # Skip every other frame for efficiency

        #check_and_add_new_profiles()

        # Detect humans using YOLO
        results = yolo_model(frame)
        human_bboxes = []
       
        frame_box = []
        
        for result in results:
            for box in result.boxes:
                cls = int(box.cls[0])  # Class ID
                if cls == 0:  # YOLO class 0 = "person"
                    x1, y1, x2, y2 = map(int, box.xyxy[0])  # Bounding box coordinates
                    human_bboxes.append((x1, y1, x2, y2))

                    bounding_box.append(x1,y1,x2,y2)

                    # Draw human bounding box (Blue)
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)

        frame_count += 1

        out.write(frame)

    video_capture.release()
    out.release()
    cv2.destroyAllWindows()

    final_output_filename =f"{original_video_name}.mp4"  #f"{1 if unknown_detected else 0}_{original_video_name}.mp4"
    final_output_path = os.path.join(OUTPUT_VIDEO_FOLDER, final_output_filename)
    os.rename(output_path, final_output_path)
    print(f"Output video saved at {final_output_path}")

    save_to_excel(final_output_filename)



def save_to_excel(filename):
    print("Edit csv")
    if not os.path.exists(EXCEL_SHEET_PATH):
        with open(EXCEL_SHEET_PATH, 'w', newline='') as file:
            writer = csv.writer(file)
            #for row in data:
            writer.writerow([filename])   
        return


    # Append the new filename to the Excel sheet
    '''
    df = pd.read_excel(EXCEL_SHEET_PATH)
    df = pd.concat([df, pd.DataFrame([{"Video Name": filename}])], ignore_index=True)
    df.to_excel(EXCEL_SHEET_PATH, index=False)
    print(f"Saved {filename} to {EXCEL_SHEET_PATH}")
    '''
    #add in error checking in filename - if video not able to be processed correctly
    with open(EXCEL_SHEET_PATH, 'a', newline='') as file:
        writer = csv.writer(file)
        #for row in data:
        writer.writerow([filename])   


#process_video('/rewrite_these_twinks/testvideo.mp4')
get_all_recorded_video_names()
troll_for_videos()

