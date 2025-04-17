#!/bin/bash
cd /home/camcs/server

# Cleanup function triggered on Ctrl+C or script exit
cleanup() {
  echo "Cleaning up..."
  kill $HOST_PID 2>/dev/null
  docker stop yolo_service >/dev/null
  docker rm yolo_service >/dev/null
  pkill -f "python3 main.py"
  exit 0
}

# Catch Ctrl+C (SIGINT), script termination (SIGTERM), or normal exit
trap cleanup SIGINT SIGTERM EXIT

# Start main.py in the background
python3 main.py &
HOST_PID=$!

# Start Docker container in detached mode
docker run -d --name yolo_service \
  -v /home/camcs/server/:/server \
  ultralytics/ultralytics:latest-jetson-jetpack6 \
  python3 /server/yolo_solo.py

# Wait for main.py to finish (until Ctrl+C)
wait $HOST_PID
