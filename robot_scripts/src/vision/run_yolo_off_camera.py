#!/usr/bin/env python3
from picamera2 import Picamera2
import time

print("Initializing camera...")
picam2 = Picamera2()
config = picam2.create_preview_configuration(main={"size": (640, 640), "format": "RGB888"})
picam2.configure(config)
picam2.start()
time.sleep(2)

print("Camera ready! Starting detection...")

try:
    # Try importing Hailo's detection module
    from hailo_rpi_common import get_default_parser
    import hailo
    
    # Load YOLOv8
    model_path = "/usr/share/hailo-models/yolov8s.hef"
    detector = hailo.Detection(model_path)
    print(f"Loaded model: {model_path}")
    
    frame_count = 0
    while frame_count < 10:
        frame = picam2.capture_array()
        detections = detector.run(frame)
        
        print(f"\nFrame {frame_count}: Found {len(detections)} objects")
        for det in detections:
            print(f"  - {det}")
        
        frame_count += 1
        time.sleep(0.5)
        
except ImportError as e:
    print(f"Import error: {e}")
    print("\nTrying alternative Hailo API...")
    
    # Alternative: use hailo-rpi detection example
    import subprocess
    result = subprocess.run(['rpicam-hello', '--list-cameras'], capture_output=True, text=True)
    print(result.stdout)

except FileNotFoundError:
    print(f"Model not found at {model_path}")
    print("\nSearching for YOLOv8 models...")
    import subprocess
    result = subprocess.run(['find', '/usr', '-name', '*yolo*.hef', '-o', '-name', '*detection*.hef'], 
                          capture_output=True, text=True, timeout=10)
    print(result.stdout)

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

finally:
    picam2.stop()
    print("\nDone!")