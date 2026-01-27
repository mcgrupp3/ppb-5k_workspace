#!/usr/bin/env python3
"""
YOLOv8 Detection - Optimized for fast display
"""

import os
from picamera2 import Picamera2
import numpy as np
import cv2
import time
from hailo_platform import (HEF, VDevice, HailoStreamInterface, InferVStreams, 
                             ConfigureParams, InputVStreamParams, OutputVStreamParams,
                             FormatType, HailoSchedulingAlgorithm)

# COCO class names
COCO_CLASSES = [
    'person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus', 'train', 'truck', 'boat',
    'traffic light', 'fire hydrant', 'stop sign', 'parking meter', 'bench', 'bird', 'cat',
    'dog', 'horse', 'sheep', 'cow', 'elephant', 'bear', 'zebra', 'giraffe', 'backpack',
    'umbrella', 'handbag', 'tie', 'suitcase', 'frisbee', 'skis', 'snowboard', 'sports ball',
    'kite', 'baseball bat', 'baseball glove', 'skateboard', 'surfboard', 'tennis racket',
    'bottle', 'wine glass', 'cup', 'fork', 'knife', 'spoon', 'bowl', 'banana', 'apple',
    'sandwich', 'orange', 'broccoli', 'carrot', 'hot dog', 'pizza', 'donut', 'cake', 'chair',
    'couch', 'potted plant', 'bed', 'dining table', 'toilet', 'tv', 'laptop', 'mouse',
    'remote', 'keyboard', 'cell phone', 'microwave', 'oven', 'toaster', 'sink', 'refrigerator',
    'book', 'clock', 'vase', 'scissors', 'teddy bear', 'hair drier', 'toothbrush'
]

def preprocess_frame(frame):
    """Preprocess for YOLOv8 - letterbox, keep RGB"""
    # Hailo models typically expect RGB (not BGR like OpenCV defaults)
    # Picamera2 already gives us RGB, so just letterbox it
    
    h, w = frame.shape[:2]
    scale = min(640 / h, 640 / w)
    new_h, new_w = int(h * scale), int(w * scale)
    
    resized = cv2.resize(frame, (new_w, new_h))
    letterbox = np.full((640, 640, 3), 114, dtype=np.uint8)
    
    top = (640 - new_h) // 2
    left = (640 - new_w) // 2
    letterbox[top:top+new_h, left:left+new_w] = resized
    
    return letterbox

def parse_detections(output_data, conf_threshold=0.03):
    """Parse Hailo output - coordinates are NORMALIZED (0-1), need scaling"""
    detections = []
    
    # Frame dimensions
    FRAME_WIDTH = 640
    FRAME_HEIGHT = 480
    
    # Unwrap nested list
    if isinstance(output_data, list) and len(output_data) > 0:
        if isinstance(output_data[0], list):
            output_data = output_data[0]
    
    # Parse per-class arrays
    for class_id, class_dets in enumerate(output_data):
        if not isinstance(class_dets, np.ndarray) or class_dets.shape[0] == 0:
            continue
        
        for det in class_dets:
            confidence, y_min, x_min, y_max, x_max = det
            
            # Lower threshold for person class (class_id 0)
            threshold = 0.02 if class_id == 0 else conf_threshold
            
            if confidence < threshold:
                continue
            
            # CRITICAL: Coordinates are normalized (0-1), multiply by frame size
            x_min_px = x_min * FRAME_WIDTH
            x_max_px = x_max * FRAME_WIDTH
            y_min_px = y_min * FRAME_HEIGHT
            y_max_px = y_max * FRAME_HEIGHT
            
            detections.append({
                'bbox': [float(x_min_px), float(y_min_px), float(x_max_px), float(y_max_px)],
                'confidence': float(confidence),
                'class_id': int(class_id),
                'class_name': COCO_CLASSES[class_id]
            })
    
    return sorted(detections, key=lambda x: x['confidence'], reverse=True)

def draw_detections(frame, detections):
    """Draw boxes on frame with debugging"""
    drawn_count = 0
    
    for i, det in enumerate(detections):
        x1, y1, x2, y2 = [int(round(v)) for v in det['bbox']]
        
        # Fix coordinate order
        x1, x2 = min(x1, x2), max(x1, x2)
        y1, y2 = min(y1, y2), max(y1, y2)
        
        # Clamp to frame
        h, w = frame.shape[:2]
        x1 = max(0, min(x1, w-1))
        x2 = max(0, min(x2, w-1))
        y1 = max(0, min(y1, h-1))
        y2 = max(0, min(y2, h-1))
        
        # Check box size
        box_w = x2 - x1
        box_h = y2 - y1
        
        if box_w < 5 or box_h < 5:
            print(f"  WARNING: Box {i} too small ({box_w}x{box_h}), skipping")
            continue
        
        # Color: green for people, blue for others
        color = (0, 255, 0) if det['class_name'] == 'person' else (255, 0, 0)
        
        # Draw VERY thick box for visibility
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 6)
        
        # Label with large background
        label = f"{det['class_name']} {det['confidence']:.2f}"
        font_scale = 0.9
        thickness = 2
        (label_w, label_h), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
        
        # Background for text
        cv2.rectangle(frame, (x1, y1-label_h-20), (x1+label_w+20, y1), (0, 0, 0), -1)
        
        # Text
        cv2.putText(frame, label, (x1+10, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 
                   font_scale, color, thickness)
        
        drawn_count += 1
    
    if drawn_count > 0:
        print(f"  Drew {drawn_count} bounding boxes")
    
    return frame

def main():
    print("="*60)
    print("YOLOv8 Detection - Simple File Stream")
    print("="*60)
    
    print(f"\nWorking directory: {os.getcwd()}")
    print(f"Files will be saved here: {os.path.abspath('.')}")
    
    # Initialize camera
    print("\n[1/4] Initializing camera...")
    picam2 = Picamera2()
    config = picam2.create_preview_configuration(main={"size": (640, 480), "format": "RGB888"})
    picam2.configure(config)
    picam2.start()
    time.sleep(2)
    print("✓ Camera ready")
    
    # Load model
    print("\n[2/4] Loading Hailo model...")
    params = VDevice.create_params()
    params.scheduling_algorithm = HailoSchedulingAlgorithm.ROUND_ROBIN
    
    with VDevice(params) as target:
        hef = HEF("/usr/share/hailo-models/yolov8s_h8.hef")
        configure_params = ConfigureParams.create_from_hef(hef, interface=HailoStreamInterface.PCIe)
        network_group = target.configure(hef, configure_params)[0]
        
        input_params = InputVStreamParams.make(network_group, format_type=FormatType.UINT8)
        output_params = OutputVStreamParams.make(network_group, format_type=FormatType.FLOAT32)
        print("✓ Model loaded")
        
        # Start inference
        print("\n[3/4] Starting inference pipeline...")
        with InferVStreams(network_group, input_params, output_params) as infer:
            input_name = list(input_params.keys())[0]
            print("✓ Pipeline ready")
            
            print("\n[4/4] Running detection...")
            print(f"\nSaving files to: {os.getcwd()}")
            print("  - live.jpg (updates every frame for smooth viewing)")
            print("  - debug_NNNN.jpg (saved when detections found)")
            print("\n** FOR SMOOTH DISPLAY, USE FEH IN ANOTHER TERMINAL: **")
            print("   feh --reload 0.1 --fullscreen --auto-zoom live.jpg")
            print("\nPress Ctrl+C to stop")
            print("="*60 + "\n")
            
            frame_count = 0
            start_time = time.time()
            
            try:
                while True:
                    # Capture
                    frame = picam2.capture_array()
                    
                    # Preprocess
                    preprocessed = preprocess_frame(frame)
                    
                    # Inference
                    t0 = time.time()
                    output = infer.infer({input_name: preprocessed[np.newaxis, :, :, :]})
                    inference_ms = (time.time() - t0) * 1000
                    
                    # Parse
                    output_raw = list(output.values())[0]
                    detections = parse_detections(output_raw)
                    
                    # Debug first few detections
                    if len(detections) > 0 and frame_count % 50 == 0:
                        print(f"\nDEBUG: Detection coordinates for frame {frame_count}")
                        for i, det in enumerate(detections[:2]):
                            print(f"  Detection {i}: {det['class_name']}")
                            print(f"    Raw bbox: {det['bbox']}")
                            print(f"    Confidence: {det['confidence']:.3f}")
                    
                    # Debug: Show raw detection info
                    if frame_count < 3 and len(detections) > 0:
                        print(f"\nDEBUG: Found {len(detections)} detections")
                        for det in detections[:2]:
                            print(f"  {det}")
                    
                    # Draw - ALWAYS draw even if no detections
                    display = frame.copy()
                    
                    if len(detections) > 0:
                        display = draw_detections(display, detections)
                        
                        # Add a red border around entire frame when detections found
                        h, w = display.shape[:2]
                        cv2.rectangle(display, (0, 0), (w-1, h-1), (255, 0, 0), 10)
                    
                    # Add info overlay
                    fps = frame_count / (time.time() - start_time) if frame_count > 0 else 0
                    info = f"FPS: {fps:.1f} | Inference: {inference_ms:.1f}ms | Objects: {len(detections)}"
                    cv2.rectangle(display, (5, 5), (550, 40), (0, 0, 0), -1)
                    cv2.putText(display, info, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 
                               0.6, (255, 255, 255), 2)
                    
                    # Add frame counter in corner
                    counter_text = f"Frame: {frame_count}"
                    cv2.putText(display, counter_text, (10, 460), cv2.FONT_HERSHEY_SIMPLEX,
                               0.6, (0, 255, 255), 2)
                    
                    # Write to file - with error checking
                    try:
                        # Frame is already RGB from picamera2, convert to BGR for saving
                        save_frame = cv2.cvtColor(display, cv2.COLOR_RGB2BGR)
                        
                        # Write live.jpg
                        success = cv2.imwrite('live.jpg', save_frame)
                        if not success:
                            print(f"ERROR: Failed to write live.jpg!")
                        elif frame_count == 1 or frame_count % 100 == 0:
                            print(f"✓ Writing live.jpg (frame {frame_count})")
                        
                        # Also write a timestamped copy for debugging
                        if len(detections) > 0:
                            debug_file = f'debug_{frame_count:04d}.jpg'
                            cv2.imwrite(debug_file, save_frame)
                            print(f"✓ Saved {debug_file} with {len(detections)} detection(s)")
                                
                    except Exception as e:
                        print(f"ERROR writing files: {e}")
                    
                    # Print status (reduce console spam)
                    if len(detections) > 0:
                        print(f"Frame {frame_count:4d} | FPS: {fps:5.1f} | {len(detections)} detections")
                        for det in detections[:3]:
                            bbox = det['bbox']
                            print(f"  - {det['class_name']:15s} {det['confidence']:.2f}")
                    elif frame_count % 100 == 0:
                        print(f"Frame {frame_count:4d} | FPS: {fps:5.1f} | No detections")
                    
                    frame_count += 1
                    
                    # Small delay to prevent maxing out CPU (optional, remove for max speed)
                    # time.sleep(0.001)
                    
            except KeyboardInterrupt:
                print("\n\nStopping...")
            
            # Stats
            total_time = time.time() - start_time
            print("\n" + "="*60)
            print(f"Processed {frame_count} frames in {total_time:.1f}s")
            print(f"Average FPS: {frame_count/total_time:.1f}")
            print("="*60)
    
    picam2.stop()
    print("\nDone!")

if __name__ == "__main__":
    main()