import os
from pathlib import Path

from lecture_split import main

PROJECT_DIR = Path(__file__).parent.parent
# Add ffmpeg to PATH so it can be used
os.environ['PATH'] += f";{PROJECT_DIR.joinpath('ffmpeg/bin')}"

TEST_VIDEO = PROJECT_DIR / "tests" / "testdata" / "lecture.mp4"


def test_detect_scenes():
    scenes = main.detect_scenes(video_pth=TEST_VIDEO, scene_detection_threshold=5, min_scene_length=100, frame_skip=50)
