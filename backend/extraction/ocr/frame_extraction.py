"""
Pulls still frames out of a reel video at a fixed time interval, so OCR
can run on each one. Reels often show on-screen text for a couple of
seconds at a time, so we don't need every single frame — one per second
is a reasonable starting point.
"""

import os
import cv2


def extract_frames(video_path, output_dir, interval_seconds=1):
    """
    Extract frames from a video at a fixed interval, saving them as .jpg
    images in output_dir.

    Returns a list of (frame_path, timestamp_seconds) tuples, in order.
    """
    os.makedirs(output_dir, exist_ok=True)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Could not open video file: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    if not fps or fps <= 0:
        fps = 30  # fallback if the video's metadata doesn't report fps correctly

    frame_interval = max(1, int(fps * interval_seconds))
    frames = []
    frame_count = 0
    saved_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break  # end of video

        if frame_count % frame_interval == 0:
            timestamp = frame_count / fps
            frame_filename = os.path.join(output_dir, f"frame_{saved_count:04d}.jpg")
            cv2.imwrite(frame_filename, frame)
            frames.append((frame_filename, timestamp))
            saved_count += 1

        frame_count += 1

    cap.release()
    return frames