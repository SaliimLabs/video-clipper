# video-clipper

A single-file Python tool that cuts a long 16:9 video into short clips, optionally with burned-in captions. It is the tool [ClutchClip](https://github.com/SaliimLabs/ClutchClip-releases) grew out of.

Published as a work sample. See `LICENSE`, which is read-only.

## What it does

Point it at a folder holding one or more source videos and a `timestamps.txt`, and it will produce:

- **9:16 vertical clips**, with the 16:9 source centered over a blurred fill of itself
- **16:9 horizontal clips**
- or both

Captions are optional. When enabled, Whisper transcribes with word-level timestamps and the tool burns the result in using one of four presets: Clean White, Big Viral Yellow, Comic White, and Comic Yellow Box.

It can also generate a subtitle file for a full-length video without cutting anything, which is the useful path for long YouTube uploads.

## Usage

Drop the script in a folder with your video and a `timestamps.txt`:

```
0:15 - 0:45
1:23 - 2:10
```

Then run it and answer the prompts:

```
python video_clipper.py
```

It walks you through picking the source video, the encoder, the output format, and the caption style. Output lands in a directory named for what you chose, such as `clips_9x16_captions/`.

## Requirements

- Python 3.9 or newer
- [`ffmpeg`](https://ffmpeg.org/) on your `PATH`
- [`openai-whisper`](https://github.com/openai/whisper), only if you want captions. It is imported lazily, so the tool runs without it as long as captions are off.

An NVIDIA GPU is detected and offered as `h264_nvenc`. Without one it falls back to `libx264` on the CPU.

## Notes on the code

The whole thing is standard library plus two subprocess boundaries, `ffmpeg` and Whisper. There is no config file and no framework. That was deliberate: the tool needed to survive being copied into a random folder on a machine that had never run it before.
