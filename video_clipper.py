#!/usr/bin/env python3
"""
Unified Video Clipper

Creates timestamp-based clips from 16:9 source videos and can generate
full-video subtitle files for long YouTube videos.

Supported outputs:
  1. 9:16 vertical clips with blurred background and centered 16:9 video
  2. 16:9 horizontal clips
  3. Both output formats

Captions are optional and generated with Whisper when enabled.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


VIDEO_EXTENSIONS = (".mp4", ".mov", ".avi", ".mkv", ".m4v")
TIMESTAMPS_FILE = "timestamps.txt"
WHISPER_MODEL = "small"

OUTPUT_DIRS = {
    ("9x16", True): "clips_9x16_captions",
    ("9x16", False): "clips_9x16_no_captions",
    ("16x9", True): "clips_16x9_captions",
    ("16x9", False): "clips_16x9_no_captions",
}

FULL_VIDEO_SUBTITLE_DIR = "full_video_subtitles"

ENCODERS = [
    {
        "name": "CPU - libx264",
        "key": "cpu",
        "description": "Best compatibility, slower exports.",
    },
    {
        "name": "NVIDIA GPU - h264_nvenc",
        "key": "nvidia",
        "description": "Faster exports if your NVIDIA GPU/driver supports NVENC.",
    },
]

ASS_COLORS = {
    "white": "&H00FFFFFF",
    "yellow": "&H0000FFFF",
    "cyan": "&H00FFFF00",
    "orange": "&H000080FF",
    "lime": "&H0000FF00",
    "red": "&H000000FF",
    "pink": "&H00FF66FF",
    "blue": "&H00FF9900",
    "black": "&H00000000",
    "dark blue": "&H00402000",
    "purple": "&H00802080",
}

BACKGROUND_COLORS = {
    "none": None,
    "black 50%": "&H80000000",
    "black 70%": "&H4D000000",
    "blue 60%": "&H660F2A5F",
    "purple 60%": "&H665F1A5F",
}

CAPTION_FONTS = [
    "Bangers",
    "Luckiest Guy",
    "Bungee",
    "Bowlby One SC",
    "Chewy",
    "Carter One",
    "Titan One",
    "Sigmar One",
    "Ranchers",
    "Knewave",
    "Freckle Face",
    "Patrick Hand",
    "Comic Neue",
    "Permanent Marker",
    "Anton",
    "Archivo Black",
    "Bebas Neue",
    "Montserrat Alternates",
    "Oswald",
    "Righteous",
    "Inter",
    "Impact",
    "Arial",
    "Comic Sans MS",
]

CAPTION_SIZES = {
    "small": 42,
    "medium": 54,
    "large": 66,
    "extra large": 78,
}

OUTLINE_SIZES = {
    "none": 0,
    "thin": 2,
    "medium": 4,
    "thick": 6,
}

CAPTION_PRESETS = [
    {
        "name": "Clean White",
        "font": "Inter",
        "text_color": "white",
        "outline_color": "black",
        "outline": "medium",
        "background": "none",
        "size": "medium",
        "uppercase": False,
        "description": "Clean readable captions for most videos.",
    },
    {
        "name": "Big Viral Yellow",
        "font": "Luckiest Guy",
        "text_color": "yellow",
        "outline_color": "black",
        "outline": "thick",
        "background": "none",
        "size": "large",
        "uppercase": True,
        "description": "Large yellow social captions with heavy outline.",
    },
    {
        "name": "Comic White",
        "font": "Bangers",
        "text_color": "white",
        "outline_color": "black",
        "outline": "thick",
        "background": "none",
        "size": "large",
        "uppercase": True,
        "description": "Comic-style white captions for energetic clips.",
    },
    {
        "name": "Comic Yellow Box",
        "font": "Chewy",
        "text_color": "yellow",
        "outline_color": "black",
        "outline": "thin",
        "background": "black 50%",
        "size": "medium",
        "uppercase": False,
        "description": "Fun rounded captions with a translucent black box.",
    },
    {
        "name": "News Box",
        "font": "Archivo Black",
        "text_color": "white",
        "outline_color": "black",
        "outline": "thin",
        "background": "blue 60%",
        "size": "medium",
        "uppercase": False,
        "description": "More polished caption box for news-style clips.",
    },
    {
        "name": "High Contrast Box",
        "font": "Arial",
        "text_color": "white",
        "outline_color": "black",
        "outline": "thin",
        "background": "black 70%",
        "size": "large",
        "uppercase": False,
        "description": "Maximum readability over busy footage.",
    },
]


def run_command(cmd: list[str], error_label: str) -> bool:
    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return True
    except subprocess.CalledProcessError as exc:
        print(f"\nERROR: {error_label}")
        if exc.stderr:
            print(exc.stderr.strip())
        return False


def check_ffmpeg() -> bool:
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def check_whisper() -> bool:
    try:
        import whisper  # noqa: F401

        return True
    except ImportError:
        return False


def check_encoder_available(encoder_key: str) -> bool:
    if encoder_key == "cpu":
        return True
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                "testsrc2=size=1280x720:rate=30",
                "-t",
                "0.1",
                *video_encode_args(encoder_key),
                "-f",
                "null",
                "-",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def video_encode_args(encoder_key: str) -> list[str]:
    if encoder_key == "nvidia":
        return [
            "-c:v",
            "h264_nvenc",
            "-preset",
            "p5",
            "-rc",
            "vbr",
            "-cq",
            "20",
            "-b:v",
            "0",
        ]
    return [
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "20",
    ]


def parse_timestamp(timestamp_str: str) -> float:
    parts = timestamp_str.strip().split(":")
    if not parts or any(part.strip() == "" for part in parts):
        raise ValueError(f"Invalid timestamp: {timestamp_str}")

    numbers = [int(part) for part in parts]
    if len(numbers) == 1:
        return float(numbers[0])
    if len(numbers) == 2:
        return float(numbers[0] * 60 + numbers[1])
    if len(numbers) == 3:
        return float(numbers[0] * 3600 + numbers[1] * 60 + numbers[2])
    raise ValueError(f"Invalid timestamp: {timestamp_str}")


def read_timestamps(timestamp_file: Path) -> list[tuple[float, float]]:
    clips: list[tuple[float, float]] = []
    with timestamp_file.open("r", encoding="utf-8") as file:
        for line_num, raw_line in enumerate(file, 1):
            line = raw_line.split("#", 1)[0].strip()
            if not line:
                continue
            if "-" not in line:
                print(f"Warning: line {line_num} has no '-' separator, skipping: {raw_line.strip()}")
                continue

            start_str, end_str = line.split("-", 1)
            try:
                start = parse_timestamp(start_str)
                end = parse_timestamp(end_str)
            except ValueError as exc:
                print(f"Warning: line {line_num} has invalid timestamp, skipping: {raw_line.strip()}")
                print(f"  {exc}")
                continue

            if end <= start:
                print(f"Warning: line {line_num} ends before it starts, skipping: {raw_line.strip()}")
                continue

            clips.append((start, end))
    return clips


def seconds_label(seconds: float) -> str:
    whole = int(seconds)
    hours = whole // 3600
    minutes = (whole % 3600) // 60
    secs = whole % 60
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def find_videos(folder: Path) -> list[Path]:
    videos = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS]
    return sorted(videos, key=lambda p: p.name.lower())


def choose_from_menu(prompt: str, options: list[str]) -> int:
    while True:
        print()
        print(prompt)
        for index, option in enumerate(options, 1):
            print(f"  {index}. {option}")
        choice = input("Enter number: ").strip()
        try:
            selected = int(choice)
        except ValueError:
            print("Please enter a number from the list.")
            continue
        if 1 <= selected <= len(options):
            return selected - 1
        print("Please enter a number from the list.")


def choose_yes_no(prompt: str) -> bool:
    index = choose_from_menu(prompt, ["Yes", "No"])
    return index == 0


def choose_video(videos: list[Path]) -> Path:
    if len(videos) == 1:
        print(f"Using video: {videos[0].name}")
        return videos[0]
    index = choose_from_menu("Multiple videos found. Which one should be clipped?", [video.name for video in videos])
    return videos[index]


def describe_style(style: dict[str, object]) -> list[str]:
    return [
        f"Font: {style['font']}",
        f"Text color: {style['text_color']}",
        f"Outline: {style['outline']} {style['outline_color']}",
        f"Background: {style['background']}",
        f"Size: {style['size']}",
        f"Case: {'UPPERCASE' if style['uppercase'] else 'Original case'}",
        "Position: bottom",
    ]


def choose_preset_style() -> dict[str, object]:
    while True:
        print()
        print("Preset caption styles:")
        for index, preset in enumerate(CAPTION_PRESETS, 1):
            print()
            print(f"{index}. {preset['name']}")
            print(f"   {preset['description']}")
            for line in describe_style(preset):
                print(f"   {line}")
        choice = input("\nEnter preset number: ").strip()
        try:
            selected = int(choice)
        except ValueError:
            print("Please enter a preset number.")
            continue
        if 1 <= selected <= len(CAPTION_PRESETS):
            return dict(CAPTION_PRESETS[selected - 1])
        print("Please enter a preset number.")


def choose_manual_style() -> dict[str, object]:
    font = CAPTION_FONTS[choose_from_menu("Choose caption font:", CAPTION_FONTS)]
    text_color = list(ASS_COLORS.keys())[choose_from_menu("Choose text color:", list(ASS_COLORS.keys()))]
    outline_color = list(ASS_COLORS.keys())[choose_from_menu("Choose outline color:", list(ASS_COLORS.keys()))]
    outline = list(OUTLINE_SIZES.keys())[choose_from_menu("Choose outline thickness:", list(OUTLINE_SIZES.keys()))]
    background = list(BACKGROUND_COLORS.keys())[choose_from_menu("Choose background box:", list(BACKGROUND_COLORS.keys()))]
    size = list(CAPTION_SIZES.keys())[choose_from_menu("Choose caption size:", list(CAPTION_SIZES.keys()))]
    uppercase = choose_yes_no("Make captions uppercase?")
    return {
        "name": "Manual Style",
        "font": font,
        "text_color": text_color,
        "outline_color": outline_color,
        "outline": outline,
        "background": background,
        "size": size,
        "uppercase": uppercase,
        "description": "Manual caption style.",
    }


def choose_caption_style() -> dict[str, object]:
    setup = choose_from_menu("Caption setup:", ["Use a preset style", "Build manually"])
    style = choose_preset_style() if setup == 0 else choose_manual_style()
    print()
    print("Selected caption style:")
    for line in describe_style(style):
        print(f"  {line}")
    if not choose_yes_no("Use this caption style?"):
        return choose_caption_style()
    return style


def choose_encoder() -> str:
    print()
    print("Video encoder options:")
    for index, encoder in enumerate(ENCODERS, 1):
        print(f"  {index}. {encoder['name']} - {encoder['description']}")

    selected = choose_from_menu("Choose video encoder for clip exports:", [str(encoder["name"]) for encoder in ENCODERS])
    encoder_key = str(ENCODERS[selected]["key"])
    if not check_encoder_available(encoder_key):
        print()
        print("WARNING: NVIDIA NVENC was selected, but the h264_nvenc runtime check failed.")
        print("Falling back to CPU - libx264.")
        return "cpu"
    return encoder_key


def load_whisper_model():
    import whisper

    print(f"\nLoading Whisper model: {WHISPER_MODEL}")
    print("This may take a moment, especially the first time.")
    return whisper.load_model(WHISPER_MODEL)


def transcribe_media(model, media_file: Path) -> dict[str, object]:
    print("  Transcribing with Whisper...")
    return model.transcribe(str(media_file), word_timestamps=True, fp16=False)


def extract_audio_for_transcription(input_video: Path, start: float, duration: float, output_audio: Path) -> bool:
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        str(start),
        "-i",
        str(input_video),
        "-t",
        str(duration),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        "-y",
        str(output_audio),
    ]
    return run_command(cmd, "Could not extract audio for captions.")


def transcribe_words(model, audio_file: Path) -> list[dict[str, object]]:
    result = transcribe_media(model, audio_file)
    return extract_words_from_result(result)


def extract_words_from_result(result: dict[str, object]) -> list[dict[str, object]]:
    words: list[dict[str, object]] = []
    for segment in result.get("segments", []):
        for word in segment.get("words", []):
            text = word.get("word", "").strip()
            if not text:
                continue
            words.append(
                {
                    "word": text,
                    "start": float(word.get("start", 0)),
                    "end": float(word.get("end", 0)),
                }
            )
    return words


def extract_segments_from_result(result: dict[str, object]) -> list[dict[str, object]]:
    segments: list[dict[str, object]] = []
    for segment in result.get("segments", []):
        text = str(segment.get("text", "")).strip()
        if not text:
            continue
        segments.append(
            {
                "text": text,
                "start": float(segment.get("start", 0)),
                "end": float(segment.get("end", 0)),
            }
        )
    return segments


def format_ass_time(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centiseconds = int((seconds % 1) * 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centiseconds:02d}"


def format_srt_time(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    milliseconds = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def escape_ass_text(text: str, uppercase: bool) -> str:
    if uppercase:
        text = text.upper()
    text = text.replace("\n", " ").replace("\r", " ")
    text = text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
    return text


def escape_srt_text(text: str) -> str:
    return text.replace("\r", " ").replace("\n", " ").strip()


def create_ass_subtitle_file(
    words: list[dict[str, object]],
    output_path: Path,
    style: dict[str, object],
    output_format: str,
) -> Path:
    if output_format == "9x16":
        play_res_x, play_res_y, margin_v = 1080, 1920, 120
    else:
        play_res_x, play_res_y, margin_v = 1920, 1080, 70

    background = str(style["background"])
    has_box = background != "none"
    border_style = 3 if has_box else 1
    outline_width = OUTLINE_SIZES[str(style["outline"])]
    box_padding = max(8, outline_width * 2) if has_box else outline_width
    back_color = BACKGROUND_COLORS[background] or "&HFF000000"

    ass_header = f"""[Script Info]
Title: Video Clipper Captions
ScriptType: v4.00+
PlayResX: {play_res_x}
PlayResY: {play_res_y}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{style['font']},{CAPTION_SIZES[str(style['size'])]},{ASS_COLORS[str(style['text_color'])]},&H000000FF,{ASS_COLORS[str(style['outline_color'])]},{back_color},-1,0,0,0,100,100,0,0,{border_style},{box_padding},0,2,60,60,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    dialogues = []
    for word in words:
        start = format_ass_time(float(word["start"]))
        end = format_ass_time(float(word["end"]))
        text = escape_ass_text(str(word["word"]), bool(style["uppercase"]))
        dialogues.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")

    output_path.write_text(ass_header + "\n".join(dialogues), encoding="utf-8")
    return output_path


def create_srt_subtitle_file(segments: list[dict[str, object]], output_path: Path) -> Path:
    blocks = []
    for index, segment in enumerate(segments, 1):
        start = format_srt_time(float(segment["start"]))
        end = format_srt_time(float(segment["end"]))
        text = escape_srt_text(str(segment["text"]))
        blocks.append(f"{index}\n{start} --> {end}\n{text}")
    output_path.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")
    return output_path


def create_ass_subtitle_file_from_segments(
    segments: list[dict[str, object]],
    output_path: Path,
    style: dict[str, object],
) -> Path:
    entries = [
        {
            "word": segment["text"],
            "start": segment["start"],
            "end": segment["end"],
        }
        for segment in segments
    ]
    return create_ass_subtitle_file(entries, output_path, style, "16x9")


def escape_ffmpeg_filter_path(path: Path) -> str:
    return str(path).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def burn_captions(input_video: Path, ass_file: Path, output_video: Path, encoder_key: str) -> bool:
    ass_path = escape_ffmpeg_filter_path(ass_file)
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(input_video),
        "-vf",
        f"ass='{ass_path}'",
        *video_encode_args(encoder_key),
        "-c:a",
        "copy",
        "-movflags",
        "+faststart",
        "-y",
        str(output_video),
    ]
    return run_command(cmd, f"Could not burn captions into {output_video.name}.")


def create_9x16_clip(input_video: Path, start: float, duration: float, output_file: Path, encoder_key: str) -> bool:
    filter_complex = (
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,gblur=sigma=20[bg];"
        "[0:v]scale=-2:1080[fg];"
        "[bg][fg]overlay=(W-w)/2:(H-h)/2[v]"
    )
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        str(start),
        "-i",
        str(input_video),
        "-t",
        str(duration),
        "-filter_complex",
        filter_complex,
        "-map",
        "[v]",
        "-map",
        "0:a?",
        *video_encode_args(encoder_key),
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        "-y",
        str(output_file),
    ]
    return run_command(cmd, f"Could not create 9:16 clip {output_file.name}.")


def create_16x9_clip(input_video: Path, start: float, duration: float, output_file: Path, encoder_key: str) -> bool:
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        str(start),
        "-i",
        str(input_video),
        "-t",
        str(duration),
        "-vf",
        "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2",
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        *video_encode_args(encoder_key),
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        "-y",
        str(output_file),
    ]
    return run_command(cmd, f"Could not create 16:9 clip {output_file.name}.")


def create_base_clip(
    output_format: str,
    input_video: Path,
    start: float,
    duration: float,
    output_file: Path,
    encoder_key: str,
) -> bool:
    if output_format == "9x16":
        return create_9x16_clip(input_video, start, duration, output_file, encoder_key)
    return create_16x9_clip(input_video, start, duration, output_file, encoder_key)


def process_output_format(
    output_format: str,
    input_video: Path,
    start: float,
    duration: float,
    output_file: Path,
    captions_enabled: bool,
    words: list[dict[str, object]],
    style: dict[str, object] | None,
    temp_dir: Path,
    encoder_key: str,
) -> bool:
    if not captions_enabled:
        return create_base_clip(output_format, input_video, start, duration, output_file, encoder_key)

    temp_base = temp_dir / f"{output_file.stem}_{output_format}_base.mp4"
    if not create_base_clip(output_format, input_video, start, duration, temp_base, encoder_key):
        return False

    if not words:
        print("  No speech detected. Saving clip without captions.")
        shutil.copy2(temp_base, output_file)
        return True

    assert style is not None
    ass_file = temp_dir / f"{output_file.stem}_{output_format}.ass"
    create_ass_subtitle_file(words, ass_file, style, output_format)
    return burn_captions(temp_base, ass_file, output_file, encoder_key)


def print_summary_header() -> None:
    print("=" * 70)
    print("UNIFIED VIDEO CLIPPER")
    print("=" * 70)
    print("Creates timestamped clips or full-video subtitle files.")
    print("Clip captions and YouTube subtitle files are generated with Whisper.")


def process_timestamped_clips(cwd: Path, input_video: Path) -> int:
    timestamp_path = cwd / TIMESTAMPS_FILE
    if not timestamp_path.exists():
        print(f"\nERROR: {TIMESTAMPS_FILE} was not found in this folder.")
        print("Create a timestamps.txt file like:")
        print("  0:15 - 0:45")
        print("  1:23 - 2:10")
        return 1

    clips = read_timestamps(timestamp_path)
    if not clips:
        print(f"\nERROR: No valid timestamps were found in {TIMESTAMPS_FILE}.")
        return 1

    encoder_key = choose_encoder()

    format_choice = choose_from_menu(
        "What do you want to create?",
        ["9:16 vertical social clips", "16:9 horizontal clips", "Both 9:16 and 16:9 clips"],
    )
    output_formats = ["9x16"] if format_choice == 0 else ["16x9"] if format_choice == 1 else ["9x16", "16x9"]

    captions_enabled = choose_yes_no("Add auto-generated Whisper captions?")
    caption_style = None
    whisper_model = None
    if captions_enabled:
        if not check_whisper():
            print("\nERROR: Whisper is not installed.")
            print("Install it with: python -m pip install openai-whisper")
            return 1
        caption_style = choose_caption_style()
        whisper_model = load_whisper_model()

    output_dirs: dict[str, Path] = {}
    for output_format in output_formats:
        output_dir = cwd / OUTPUT_DIRS[(output_format, captions_enabled)]
        output_dir.mkdir(exist_ok=True)
        output_dirs[output_format] = output_dir

    print()
    print("Ready to process:")
    print(f"  Video: {input_video.name}")
    print(f"  Timestamps: {timestamp_path.name}")
    print(f"  Clips: {len(clips)}")
    print(f"  Formats: {', '.join(output_formats)}")
    print(f"  Captions: {'Yes' if captions_enabled else 'No'}")
    print(f"  Encoder: {'NVIDIA GPU - h264_nvenc' if encoder_key == 'nvidia' else 'CPU - libx264'}")
    for output_format, output_dir in output_dirs.items():
        print(f"  {output_format} output: {output_dir.name}/")

    if not choose_yes_no("Start processing now?"):
        print("Cancelled.")
        return 0

    successful = 0
    failed = 0

    temp_dir = cwd / f"_video_clipper_work_{os.getpid()}"
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(exist_ok=True)
    try:
        for clip_index, (start, end) in enumerate(clips, 1):
            duration = end - start
            print()
            print("-" * 70)
            print(f"Clip {clip_index}/{len(clips)}: {seconds_label(start)} - {seconds_label(end)}")

            words: list[dict[str, object]] = []
            if captions_enabled:
                audio_file = temp_dir / f"clip_{clip_index:03d}_audio.wav"
                if extract_audio_for_transcription(input_video, start, duration, audio_file):
                    assert whisper_model is not None
                    words = transcribe_words(whisper_model, audio_file)
                    print(f"  Caption words found: {len(words)}")
                else:
                    print("  Continuing without captions for this clip.")

            for output_format in output_formats:
                output_file = output_dirs[output_format] / f"clip_{clip_index:03d}.mp4"
                print(f"  Creating {output_format}: {output_file}")
                ok = process_output_format(
                    output_format,
                    input_video,
                    start,
                    duration,
                    output_file,
                    captions_enabled,
                    words,
                    caption_style,
                    temp_dir,
                    encoder_key,
                )
                if ok:
                    successful += 1
                    print(f"  Finished {output_format}: {output_file.name}")
                else:
                    failed += 1
                    print(f"  Failed {output_format}: {output_file.name}")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    print()
    print("=" * 70)
    print("COMPLETE")
    print("=" * 70)
    print(f"Successful outputs: {successful}")
    print(f"Failed outputs: {failed}")
    for output_format, output_dir in output_dirs.items():
        print(f"{output_format}: {output_dir.resolve()}")
    return 0 if failed == 0 else 1


def choose_full_video_subtitle_outputs() -> list[str]:
    output_choice = choose_from_menu(
        "Full-video subtitle output:",
        [
            "Create .srt subtitle file only - recommended for YouTube",
            "Create .ass styled subtitle file only",
            "Create both .srt and .ass subtitle files",
        ],
    )
    if output_choice == 0:
        return ["srt"]
    if output_choice == 1:
        return ["ass"]
    return ["srt", "ass"]


def process_full_video_subtitles(cwd: Path, input_video: Path) -> int:
    if not check_whisper():
        print("\nERROR: Whisper is not installed.")
        print("Install it with: python -m pip install openai-whisper")
        return 1

    subtitle_outputs = choose_full_video_subtitle_outputs()
    caption_style = choose_caption_style() if "ass" in subtitle_outputs else None

    print()
    print("Ready to create full-video subtitle file(s):")
    print(f"  Video: {input_video.name}")
    print(f"  Outputs: {', '.join('.' + item for item in subtitle_outputs)}")
    print(f"  Output folder: {FULL_VIDEO_SUBTITLE_DIR}/")
    print("  Note: this does not re-encode the video.")

    if not choose_yes_no("Start full-video transcription now?"):
        print("Cancelled.")
        return 0

    output_dir = cwd / FULL_VIDEO_SUBTITLE_DIR
    output_dir.mkdir(exist_ok=True)

    whisper_model = load_whisper_model()
    result = transcribe_media(whisper_model, input_video)
    segments = extract_segments_from_result(result)

    if not segments:
        print("\nERROR: Whisper did not return any subtitle segments.")
        return 1

    created: list[Path] = []
    output_base = output_dir / input_video.stem

    if "srt" in subtitle_outputs:
        srt_path = output_base.with_suffix(".srt")
        create_srt_subtitle_file(segments, srt_path)
        created.append(srt_path)

    if "ass" in subtitle_outputs:
        assert caption_style is not None
        ass_path = output_base.with_suffix(".ass")
        create_ass_subtitle_file_from_segments(segments, ass_path, caption_style)
        created.append(ass_path)

    print()
    print("=" * 70)
    print("COMPLETE")
    print("=" * 70)
    print(f"Subtitle segments: {len(segments)}")
    for path in created:
        print(f"Created: {path.resolve()}")
    print("\nFor YouTube, upload the .srt file with the original video.")
    return 0


def main() -> int:
    print_summary_header()

    if not check_ffmpeg():
        print("\nERROR: ffmpeg is not installed or not available in PATH.")
        return 1

    cwd = Path.cwd()
    videos = find_videos(cwd)
    if not videos:
        print("\nERROR: No video files found in this folder.")
        print(f"Supported extensions: {', '.join(VIDEO_EXTENSIONS)}")
        return 1
    input_video = choose_video(videos)

    workflow = choose_from_menu(
        "What workflow do you need?",
        [
            "Timestamped clips - 9:16, 16:9, or both",
            "Full-video YouTube subtitle file - no video re-encoding",
        ],
    )
    if workflow == 1:
        return process_full_video_subtitles(cwd, input_video)
    return process_timestamped_clips(cwd, input_video)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        raise SystemExit(130)
