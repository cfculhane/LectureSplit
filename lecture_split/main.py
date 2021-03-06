import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, List, Tuple

import pprintpp
from gooey import GooeyParser, Gooey
from scenedetect import video_splitter, FrameTimecode
from scenedetect.detectors import ContentDetector
from scenedetect.scene_manager import SceneManager
from scenedetect.video_manager import VideoManager
from tqdm import tqdm

from lecture_split.shared_logging import setup_logging

PROJECT_DIR = Path(__file__).parent.parent
# Add ffmpeg to PATH so it can be used
os.environ['PATH'] += f";{PROJECT_DIR.joinpath('ffmpeg/bin')}"

logger = logging.getLogger("LectureSplit")


def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")

    return Path(base_path, relative_path)


LOGGER_CONFIG = resource_path(PROJECT_DIR / "lecture_split" / "logging_config.yaml")


def detect_scenes(video_pth: Path, scene_detection_threshold: int, min_scene_length: int,
                  frame_skip: Optional[int], show_progress: bool = False):
    """
    Detect scenes in a video
    :param video_pth: Path to video file to process
    :param scene_detection_threshold: Threshold for detection of change in scene
    :param min_scene_length: Minimum allowed length of scene, in frames
    :param frame_skip:  Number of frames to skip, peeding up the detection time at the expense of accuracy
    :param show_progress: If true, will show a tqdm progress bar of scene detection
    :return:
    """
    time_start = time.time()
    logger.info(f"Starting detect_scene with args: \n"
                f"{video_pth=}\n{scene_detection_threshold=}\n{min_scene_length=}\n{frame_skip=}")
    video_manager = VideoManager([str(video_pth)])
    scene_manager = SceneManager()
    # Add ContentDetector algorithm (constructor takes detector options like threshold).
    scene_manager.add_detector(ContentDetector(threshold=scene_detection_threshold,
                                               min_scene_len=min_scene_length))
    base_timecode = video_manager.get_base_timecode()

    try:
        video_manager.set_downscale_factor()  # no args means default
        video_manager.start()

        scene_manager.detect_scenes(frame_source=video_manager, frame_skip=frame_skip, show_progress=show_progress)

        # Obtain list of detected scenes.
        scene_list = scene_manager.get_scene_list(base_timecode)
        time_taken = time.time() - time_start
        logger.info(f"Detection of scenes complete in {round(time_taken, 1)} seconds")
        logger.info('List of scenes obtained:')
        for i, scene in enumerate(scene_list):
            logger.info(f'    Scene {i + 1}: Start {scene[0].get_timecode()} / Frame {scene[0].get_frames()}, '
                        f'End {scene[1].get_timecode()} / Frame {scene[1].get_frames()}')
        return scene_list
    finally:
        video_manager.release()


def extract_split_audio(video_pth: Path, output_dir: Path, scene_list: List[Tuple[FrameTimecode, FrameTimecode]],
                        suppress_output: bool = True):
    """
    Extracts the audio from each of the split up scenes using ffmpeg
    :param video_pth: Path to video as input
    :param output_dir: Output dir to export audio to
    :param scene_list: SceneList created by detect_scenes()
    :param suppress_output: If True (default) will suppress output of ffmpeg
    :return:
    """
    if video_splitter.is_ffmpeg_available() is False:
        raise RuntimeError("Please install ffmpeg to ./ffmpeg!")

    audio_output_dir = output_dir / video_pth.stem
    audio_output_dir.mkdir(parents=True, exist_ok=True)

    for i, (start_time, end_time) in tqdm(enumerate(scene_list), total=len(scene_list), unit="scene", miniters=1,
                                          desc="Exporting audio"):
        duration = (end_time - start_time)
        call_list = ['ffmpeg']
        if suppress_output:
            call_list += ['-v', 'quiet']
        elif i > 0:
            # Only show ffmpeg output for the first call, which will display any
            # errors if it fails, and then break the loop. We only show error messages
            # for the remaining calls.
            call_list += ['-v', 'error']
        call_list += ['-y', '-ss', start_time.get_timecode(), '-i', f"{video_pth.absolute()}"]
        call_list += ['-strict', '-2', '-t', duration.get_timecode(),
                      f"{audio_output_dir.joinpath(video_pth.stem + f'_{i + 1}.mp3')}"]
        ret_val = subprocess.call(call_list)

        if not suppress_output and i == 0 and len(scene_list) > 1:
            logger.info('Output from ffmpeg for Scene 1 shown above, splitting remaining scenes...')
        # if ret_val != 0:
        #     break


@Gooey(default_size=(800, 600))
def main():
    parser = GooeyParser(description="LectureSplit")
    parser.add_argument('input_dir', help="Input directory containing video files to process",
                        default=str(PROJECT_DIR / "input"), widget="DirChooser")
    parser.add_argument('output_dir', help="Output directory where a new directory per video file will be created",
                        default=str(PROJECT_DIR / "output"), widget="DirChooser")
    parser.add_argument('--scene_detection_threshold',
                        help="Threshold for slide change detection. \n"
                             "1 is very sensitive, 30 is very un-sensitive, default 5",
                        default=5, type=int, required=False)
    parser.add_argument('--min_scene_length',
                        help="minimum scene length (in frames). Default 100",
                        default=100, type=int, required=False)
    parser.add_argument('--frame_skip',
                        help="Number of frames to skip, peeding up the detection time at the expense of accuracy. Default 5",
                        default=5, type=int, required=False)
    args = parser.parse_args()
    logger, log_filename = setup_logging(log_config_path=LOGGER_CONFIG, log_dir=Path(args.output_dir),
                                         module_name="LectureSplit")
    logger.info("Starting LectureSplit")

    # pprintpp.pprint(args)
    video_pths = list(Path(args.input_dir).glob("*"))
    logger.info(f"Found {len(video_pths)} videos to process: \n {pprintpp.pformat(video_pths)}")
    for video_pth in tqdm(video_pths, file=sys.stdout, desc="Processing videos", position=0, miniters=1):
        logger.info("-" * 40)
        logger.info(f"Starting processing of {video_pth}")
        logging.basicConfig(level=logging.DEBUG, filename=Path(args.output_dir) / f"{video_pth.stem}.log")

        detected_scenes = detect_scenes(video_pth=video_pth, scene_detection_threshold=args.scene_detection_threshold,
                                        min_scene_length=args.min_scene_length, frame_skip=args.frame_skip,
                                        show_progress=True)
        extract_split_audio(video_pth=video_pth, output_dir=Path(args.output_dir), scene_list=detected_scenes,
                            suppress_output=True)
        logger.info("-" * 40)

    logger.info(f"All processing complete, please check output files in {Path(args.output_dir).absolute()}")


if __name__ == "__main__":
    main()
