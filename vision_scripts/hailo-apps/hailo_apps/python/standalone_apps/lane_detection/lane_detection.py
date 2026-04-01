#!/usr/bin/env python3
import sys
from pathlib import Path

# Repo root on sys.path so `import hailo_apps` works when run as `python3 lane_detection.py`
# from this folder (without requiring pip install -e for that session).
for _repo in Path(__file__).resolve().parents:
    if (_repo / "hailo_apps" / "config" / "config_manager.py").exists():
        if str(_repo) not in sys.path:
            sys.path.insert(0, str(_repo))
        break

import multiprocessing as mp
import os
from functools import partial
from typing import Any, Callable, Optional
import numpy as np
import cv2
import threading
import argparse
import collections
from lane_detection_utils import (UFLDProcessing, check_process_errors, compute_scaled_radius)

try:
    from hailo_apps.python.core.common.hailo_logger import get_logger, init_logging, level_from_args
    from hailo_apps.python.core.common.hailo_inference import HailoInfer
    from hailo_apps.python.core.common.core import handle_and_resolve_args
    from hailo_apps.python.core.common.toolbox import init_input_source
    from hailo_apps.python.core.common.defines import (
        MAX_INPUT_QUEUE_SIZE,
        MAX_OUTPUT_QUEUE_SIZE,
        MAX_ASYNC_INFER_JOBS
    )
except ImportError as _import_err:
    sys.stderr.write(
        "\nCould not import Hailo packages (hailo_apps / hailo_platform).\n"
        "Use the hailo-apps virtualenv and complete install on the Pi:\n"
        "  cd .../vision_scripts/hailo-apps\n"
        "  source setup_env.sh\n"
        "  # If not done yet: sudo ./install.sh\n"
        "Then run lane_detection.py again (hailo_platform comes from HailoRT, e.g. hailo-all).\n\n"
    )
    raise _import_err from None

APP_NAME = Path(__file__).stem
logger = get_logger(__name__)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="UFLD_v2 inference",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--input",
        "-i",
        type=str,
        default=None,
        help=(
            "Input source for processing. Can be a file path (image or video), "
            "camera index (integer), folder path containing images, or RTSP URL. "
            "For USB cameras, use 'usb' to auto-detect or '/dev/video<X>' for a specific device. "
            "For Raspberry Pi camera, use 'rpi'. If not specified, defaults to application-specific source."
        ),
    )

    parser.add_argument(
        "--hef-path",
        "-n",
        type=str,
        default=None,
        help=(
            "Path or name of Hailo Executable Format (HEF) model file. "
            "Can be: (1) full path to .hef file, (2) model name (will search in resources), "
            "or (3) model name from available models (will auto-download if not found). "
            "If not specified, uses the default model for this application."
        ),
    )

    parser.add_argument(
        "--list-models",
        action="store_true",
        help=(
            "List all available models for this application and exit. "
            "Shows default and extra models that can be used with --hef-path."
        ),
    )

    parser.add_argument(
        "--list-inputs",
        action="store_true",
        help=(
            "List available demo inputs for this application and exit. "
            "This uses the shared resources catalog (images/videos) defined in resources_config.yaml."
        ),
    )
    
    parser.add_argument(
        "--output-dir",
        "-o",
        type=str,
        default=None,
        help=(
            "Directory where output files will be saved. "
            "When --save-output is enabled, processed images, videos, or result files will be "
            "written to this directory. If not specified, outputs are saved to a default location "
            "or the current working directory. The directory will be created if it does not exist."
        ),
    )

    parser.add_argument(
        "--show",
        action="store_true",
        help=(
            "Show a live OpenCV window with lane overlays (same idea as hailo-detect-simple on rpi). "
            "Requires a display (HDMI, or SSH with X11 forwarding / VNC). Press q to stop. "
            "Still writes output.mp4 under --output-dir unless you only need preview."
        ),
    )

    parser.add_argument(
        "--no-preview-swap-rb",
        action="store_true",
        help=(
            "With --show on the Pi camera (rpi): disable the default red/blue channel swap in the preview "
            "window. By default we swap R/B for preview only (fixes blue cast on many Pi 5 + libcamera setups). "
            "Does not change the saved output.mp4."
        ),
    )

    return parser


def parser_init():
    return build_argument_parser().parse_args()


def resolve_capture_and_metadata(input_src: str, batch_size: int = 1):
    """
    Open input via shared toolbox (supports rpi/usb/stream/video/images).

    Returns:
        cap, images, input_type, frame_width, frame_height, total_frames_or_none
    """
    cap, images, input_type = init_input_source(input_src, batch_size, None)

    if images is not None:
        if not images:
            raise ValueError(f"No images loaded from input {input_src!r}")
        frame_height, frame_width = images[0].shape[:2]
        return cap, images, input_type, frame_width, frame_height, len(images)

    if cap is None:
        raise ValueError(f"No input source could be opened for {input_src!r}")

    # cap.get() may return None on some backends (e.g. PiCamera2CaptureAdapter).
    def _cap_int(prop_id: int) -> int:
        v = cap.get(prop_id)
        if v is None:
            return 0
        try:
            return int(v)
        except (TypeError, ValueError):
            return 0

    frame_width = _cap_int(cv2.CAP_PROP_FRAME_WIDTH)
    frame_height = _cap_int(cv2.CAP_PROP_FRAME_HEIGHT)
    if frame_width <= 0 or frame_height <= 0:
        ok, frame = cap.read()
        if not ok or frame is None:
            raise ValueError(f"Cannot read frames or dimensions from input {input_src!r}")
        frame_height, frame_width = frame.shape[:2]
        if input_type == "video":
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    frame_count = _cap_int(cv2.CAP_PROP_FRAME_COUNT)
    if input_type in ("usb", "rpi", "stream") or frame_count <= 0:
        total_frames = None
    else:
        total_frames = frame_count

    return cap, images, input_type, frame_width, frame_height, total_frames


def preprocess_input(
    cap: Optional[Any],
    images: Optional[list],
    input_type: str,
    input_queue: mp.Queue,
    width: int,
    height: int,
    ufld_processing: UFLDProcessing,
    quit_event: Optional[threading.Event] = None,
) -> None:
    """
    Read video frames or images, preprocess them, and put them into the input queue for inference.

    Args:
        cap: OpenCV VideoCapture, PiCamera2 adapter, or None for image lists.
        images: List of frames when using image file/dir input, else None.
        input_type: Kind of source (video, rpi, usb, stream, images).
        input_queue (mp.Queue): Queue for input frames.
        width (int): Input frame width for resizing.
        height (int): Input frame height for resizing.
        ufld_processing (UFLDProcessing): Lane detection preprocessing class.
    """
    try:
        if images is not None:
            for frame_rgb in images:
                if quit_event is not None and quit_event.is_set():
                    input_queue.put(None)
                    return
                frame = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
                resized_frame = ufld_processing.resize(frame, height, width)
                input_queue.put(([frame], [resized_frame]))
            input_queue.put(None)
            return

        assert cap is not None
        while True:
            if quit_event is not None and quit_event.is_set():
                input_queue.put(None)
                return
            success, frame = cap.read()
            if not success or frame is None:
                break
            # Copy so async inference/postprocess never races the next camera frame mutating buffer memory.
            frame = np.ascontiguousarray(frame.copy())
            resized_frame = ufld_processing.resize(frame, height, width)
            input_queue.put(([frame], [resized_frame]))

        input_queue.put(None)
    finally:
        if cap is not None:
            cap.release()


def postprocess_output(output_queue: mp.Queue,
                       output_dir: str,
                       ufld_processing: UFLDProcessing,
                       total_frames: Optional[int],
                       show_preview: bool = False,
                       quit_event: Optional[threading.Event] = None,
                       preview_swap_rb: bool = False,
                       write_video: bool = True,
                       on_lane_frame: Optional[Callable[[list, int, int, int], None]] = None,
                       ) -> None:
    """
    Post-process inference results, draw lane detections, and write output to a video.

    Args:
        output_queue (mp.Queue): Queue for output results.
        output_dir (str): Path to the output video file.
        ufld_processing (UFLDProcessing): Lane detection post-processing class.
        write_video: If False, skip VideoWriter and ffmpeg postprocess (e.g. ZMQ-only mode).
        on_lane_frame: If set, called each frame as on_lane_frame(lanes, frame_id, width, height)
            after coordinates are computed and before drawing on the frame.
    """
    # Import tqdm here to avoid issues with multiprocessing
    from tqdm import tqdm

    width, height = ufld_processing.get_original_frame_size()

    out_path = os.path.join(output_dir, "output.mp4")
    output_video = None
    if write_video:
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        output_video = cv2.VideoWriter(out_path, fourcc, 20, (width, height))

    # Compute the scaled radius for the lane detection points
    radius = compute_scaled_radius(width, height)

    pbar = tqdm(total=total_frames, desc="Processing frames") if total_frames else tqdm(desc="Processing frames")

    frame_id = 0
    while True:
        result = output_queue.get()
        if result is None:
            break  # Exit when the sentinel value is received
        original_frame, inference_output = result
        slices = list(inference_output.values())
        output_tensor = np.concatenate(slices, axis=1)  # Shape: (1, total_features)
        lanes = ufld_processing.get_coordinates(output_tensor)

        if on_lane_frame is not None:
            on_lane_frame(lanes, frame_id, width, height)
        frame_id += 1

        for lane in lanes:
            for coord in lane:
                cv2.circle(original_frame, coord, radius, (0, 255, 0), -1)
        if output_video is not None:
            output_video.write(original_frame.astype('uint8'))
        if show_preview:
            disp = original_frame.astype(np.uint8)
            if preview_swap_rb and disp.ndim == 3 and disp.shape[2] >= 3:
                disp = disp.copy()
                disp[:, :, [0, 2]] = disp[:, :, [2, 0]]
            cv2.imshow("Lane detection", disp)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q") and quit_event is not None:
                quit_event.set()
        pbar.update(1)

    pbar.close()
    if output_video is not None:
        output_video.release()
    if show_preview:
        cv2.destroyAllWindows()

    if write_video and output_video is not None:
        # Convert to H.264 for better compatibility
        import subprocess
        logger.info("Converting video to H.264 format...")
        temp_path = out_path.replace('.mp4', '_temp.mp4')
        try:
            subprocess.run([
                'ffmpeg', '-y', '-loglevel', 'error', '-i', out_path,
                '-c:v', 'libx264', '-preset', 'medium', '-crf', '23',
                temp_path
            ], check=True, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
            os.replace(temp_path, out_path)
            logger.info("Video conversion complete!")
        except subprocess.CalledProcessError:
            logger.warning("Failed to convert video to H.264")
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except FileNotFoundError:
            logger.warning("ffmpeg not found, keeping original mp4v format")


def inference_callback(
        completion_info,
        bindings_list: list,
        input_batch: list,
        output_queue: mp.Queue
) -> None:
    """
    infernce callback to handle inference results and push them to a queue.

    Args:
        completion_info: Hailo inference completion info.
        bindings_list (list): Output bindings for each inference.
        input_batch (list): Original input frames.
        output_queue (queue.Queue): Queue to push output results to.
    """
    if completion_info.exception:
        logger.error(f'Inference error: {completion_info.exception}')
    else:
        for i, bindings in enumerate(bindings_list):
            if len(bindings._output_names) == 1:
                result = bindings.output().get_buffer()
            else:
                result = {
                    name: np.expand_dims(
                        bindings.output(name).get_buffer(), axis=0
                    )
                    for name in bindings._output_names
                }
            output_queue.put((input_batch[i], result))


def infer(hailo_inference, input_queue, output_queue):
    """
    Main inference loop that pulls data from the input queue, runs asynchronous
    inference, and pushes results to the output queue.

    Each item in the input queue is expected to be a tuple:
        (input_batch, preprocessed_batch)
        - input_batch: Original frames (used for visualization or tracking)
        - preprocessed_batch: Model-ready frames (e.g., resized, normalized)

    Args:
        hailo_inference (HailoInfer): The inference engine to run model predictions.
        input_queue (queue.Queue): Provides (input_batch, preprocessed_batch) tuples.
        output_queue (queue.Queue): Collects (input_frame, result) tuples for visualization.

    Returns:
        None
    """
    # Limit number of concurrent async inferences
    pending_jobs = collections.deque()

    while True:
        next_batch = input_queue.get()
        if not next_batch:
            break  # Stop signal received

        input_batch, preprocessed_batch = next_batch

        # Prepare the callback for handling the inference result
        inference_callback_fn = partial(
            inference_callback,
            input_batch=input_batch,
            output_queue=output_queue
        )


        while len(pending_jobs) >= MAX_ASYNC_INFER_JOBS:
            pending_jobs.popleft().wait(10000)

        # Run async inference
        job = hailo_inference.run(preprocessed_batch, inference_callback_fn)
        pending_jobs.append(job)

    # Release resources and context
    hailo_inference.close()
    output_queue.put(None)



def run_inference_pipeline(
    cap: Optional[Any],
    images: Optional[list],
    input_type: str,
    net_path: str,
    batch_size: int,
    output_dir: str,
    ufld_processing: UFLDProcessing,
    total_frames: Optional[int],
    show_preview: bool = False,
    preview_swap_rb: bool = False,
    write_video: bool = True,
    on_lane_frame: Optional[Callable[[list, int, int, int], None]] = None,
) -> None:
    """
    Run lane detection inference using HailoAsyncInference and manage the video processing pipeline.

    Args:
        cap: Video/camera capture, or None when using image list input.
        images: Image list input, or None when using cap.
        input_type: Source kind from init_input_source (e.g. video, rpi, images).
        net_path (str): Path to the HEF model file.
        batch_size (int): Number of frames per batch.
        output_dir (str): Path to save the output video.
        ufld_processing (UFLDProcessing): Lane detection processing class.
        total_frames: Frame count for progress bar, or None for live camera/stream.
        show_preview: If True, open an OpenCV window with live annotated frames.
        preview_swap_rb: If True, swap R/B in the preview only (--preview-swap-rb).
        write_video: If False, do not write output.mp4 (telemetry-only runs).
        on_lane_frame: Optional callback each frame (lanes, frame_id, width, height).
    """

    input_queue = mp.Queue(MAX_INPUT_QUEUE_SIZE)
    output_queue = mp.Queue(MAX_OUTPUT_QUEUE_SIZE)
    hailo_inference = HailoInfer(net_path, batch_size, output_type="FLOAT32")
    quit_event: Optional[threading.Event] = threading.Event() if show_preview else None

    preprocessed_frame_height, preprocessed_frame_width, _ = hailo_inference.get_input_shape()
    preprocess_thread = threading.Thread(
        target=preprocess_input,
        args=(
            cap,
            images,
            input_type,
            input_queue,
            preprocessed_frame_width,
            preprocessed_frame_height,
            ufld_processing,
            quit_event,
        ),
    )
    postprocess_thread = threading.Thread(
        target=postprocess_output,
        args=(
            output_queue,
            output_dir,
            ufld_processing,
            total_frames,
            show_preview,
            quit_event,
            preview_swap_rb,
            write_video,
            on_lane_frame,
        ),
    )

    infer_thread = threading.Thread(
        target=infer, args=(hailo_inference, input_queue, output_queue)
    )

    preprocess_thread.start()
    postprocess_thread.start()
    infer_thread.start()

    infer_thread.join()
    preprocess_thread.join()
    postprocess_thread.join()

    if write_video:
        logger.success(f"Inference was successful! Results saved in {output_dir}")
    else:
        logger.success("Inference finished (video output disabled).")



if __name__ == "__main__":

    # Parse command-line arguments
    args = parser_init()
    init_logging(level=level_from_args(args))
    handle_and_resolve_args(args, APP_NAME)
    if args.output_dir:
        os.makedirs(args.output_dir, exist_ok=True)

    if args.show:
        if sys.platform != "win32" and not os.environ.get("DISPLAY"):
            logger.warning(
                "DISPLAY is not set — cv2.imshow cannot open a window (typical over plain SSH). "
                "Use the Pi's desktop terminal, or: export DISPLAY=:0 (if a GUI session is logged in), "
                "or SSH with X11: ssh -Y user@pi, or VNC. "
                "Ensure OpenCV is GUI-capable (not opencv-python-headless only)."
            )

    try:
        cap, images, input_type, original_frame_width, original_frame_height, total_frames = (
            resolve_capture_and_metadata(args.input, 1)
        )
    except ValueError as e:
        logger.error(e)
        sys.exit(1)

    ufld_processing = UFLDProcessing(
        num_cell_row=100,
        num_cell_col=100,
        num_row=56,
        num_col=41,
        num_lanes=4,
        crop_ratio=0.8,
        original_frame_width=original_frame_width,
        original_frame_height=original_frame_height,
        total_frames=total_frames if total_frames is not None else 0,
    )

    run_inference_pipeline(
        cap,
        images,
        input_type,
        args.hef_path,
        batch_size=1,
        output_dir=args.output_dir,
        ufld_processing=ufld_processing,
        total_frames=total_frames,
        show_preview=args.show,
        preview_swap_rb=(
            args.show
            and (not args.no_preview_swap_rb)
            and (input_type == "rpi")
        ),
        write_video=True,
        on_lane_frame=None,
    )
