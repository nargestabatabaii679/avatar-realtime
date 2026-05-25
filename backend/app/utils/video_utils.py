from __future__ import annotations

import subprocess
import json
from pathlib import Path
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)

RESOLUTION_MAP = {
    "720p": "1280:720",
    "1080p": "1920:1080",
    "4k": "3840:2160",
}

BITRATE_MAP = {
    "720p": "3000k",
    "1080p": "6000k",
    "4k": "20000k",
}


async def render_final_video(
    input_path: str,
    audio_path: str,
    output_path: str,
    resolution: str = "1080p",
    options: Optional[dict] = None,
) -> None:
    """Compose final MP4 with proper resolution, audio, and codec settings."""
    options = options or {}
    scale = RESOLUTION_MAP.get(resolution, "1920:1080")
    bitrate = BITRATE_MAP.get(resolution, "6000k")
    fps = options.get("fps", 25)

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-i", audio_path,
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",
        "-b:v", bitrate,
        "-vf", f"scale={scale}:force_original_aspect_ratio=decrease,pad={scale}:(ow-iw)/2:(oh-ih)/2",
        "-r", str(fps),
        "-c:a", "aac",
        "-b:a", "192k",
        "-ar", "44100",
        "-shortest",
        "-movflags", "+faststart",
        "-pix_fmt", "yuv420p",
        output_path,
    ]

    _run_ffmpeg(cmd)
    logger.info("video_rendered", output=output_path, resolution=resolution)


async def extract_thumbnail(video_path: str, output_path: str, time_percent: float = 0.1) -> None:
    """Extract a thumbnail at the given percentage point in the video."""
    duration = await get_video_duration(video_path)
    seek_time = max(0, duration * time_percent)

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(seek_time),
        "-i", video_path,
        "-vframes", "1",
        "-q:v", "2",
        "-vf", "scale=640:-1",
        output_path,
    ]
    _run_ffmpeg(cmd)


async def get_video_duration(path: str) -> float:
    """Return video duration in seconds."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", path],
        capture_output=True, text=True,
    )
    try:
        info = json.loads(result.stdout)
        return float(info.get("format", {}).get("duration", 0))
    except Exception:
        return 0.0


async def get_video_metadata(path: str) -> dict:
    """Return complete video metadata dict."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json",
         "-show_streams", "-show_format", path],
        capture_output=True, text=True,
    )
    try:
        info = json.loads(result.stdout)
        video_stream = next(
            (s for s in info.get("streams", []) if s.get("codec_type") == "video"), {}
        )
        audio_stream = next(
            (s for s in info.get("streams", []) if s.get("codec_type") == "audio"), {}
        )
        return {
            "duration": float(info.get("format", {}).get("duration", 0)),
            "size_bytes": int(info.get("format", {}).get("size", 0)),
            "bitrate": info.get("format", {}).get("bit_rate"),
            "video_codec": video_stream.get("codec_name"),
            "width": video_stream.get("width"),
            "height": video_stream.get("height"),
            "fps": _parse_fps(video_stream.get("r_frame_rate", "25/1")),
            "audio_codec": audio_stream.get("codec_name"),
            "sample_rate": audio_stream.get("sample_rate"),
        }
    except Exception:
        return {}


def _parse_fps(fps_str: str) -> float:
    try:
        num, den = fps_str.split("/")
        return round(float(num) / float(den), 2)
    except Exception:
        return 25.0


async def extract_audio(video_path: str, output_path: str, sample_rate: int = 16000) -> None:
    """Extract audio track from video as WAV."""
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vn",
        "-ar", str(sample_rate),
        "-ac", "1",
        "-c:a", "pcm_s16le",
        output_path,
    ]
    _run_ffmpeg(cmd)


async def add_watermark(
    input_path: str,
    output_path: str,
    watermark_text: str = "AI Generated",
    position: str = "bottomright",
) -> None:
    """Add text watermark to video."""
    overlay_map = {
        "bottomright": "x=main_w-text_w-10:y=main_h-text_h-10",
        "bottomleft": "x=10:y=main_h-text_h-10",
        "topright": "x=main_w-text_w-10:y=10",
        "topleft": "x=10:y=10",
    }
    position_str = overlay_map.get(position, overlay_map["bottomright"])
    vf = (
        f"drawtext=text='{watermark_text}':fontcolor=white@0.7:fontsize=24:"
        f"bordercolor=black@0.5:borderw=2:{position_str}"
    )
    cmd = ["ffmpeg", "-y", "-i", input_path, "-vf", vf, "-c:a", "copy", output_path]
    _run_ffmpeg(cmd)


async def convert_to_hls(input_path: str, output_dir: str, resolutions: Optional[list] = None) -> str:
    """Convert MP4 to HLS multi-bitrate stream."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    playlist = out / "master.m3u8"

    resolutions = resolutions or ["720p"]
    variant_args = []

    for res in resolutions:
        scale = RESOLUTION_MAP.get(res, "1920:1080")
        bitrate = BITRATE_MAP.get(res, "4000k")
        seg_dir = out / res
        seg_dir.mkdir(exist_ok=True)
        variant_args.extend([
            f"-map", "0:v:0", f"-map", "0:a:0",
            f"-c:v:{resolutions.index(res)}", "libx264",
            f"-b:v:{resolutions.index(res)}", bitrate,
            f"-vf:v:{resolutions.index(res)}", f"scale={scale}",
        ])

    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        *variant_args,
        "-c:a", "aac", "-b:a", "128k",
        "-f", "hls",
        "-hls_time", "6",
        "-hls_playlist_type", "vod",
        "-hls_segment_filename", f"{out}/%v/seg%03d.ts",
        "-master_pl_name", "master.m3u8",
        "-var_stream_map", " ".join(f"v:{i},a:{i}" for i in range(len(resolutions))),
        str(out / "%v/playlist.m3u8"),
    ]
    _run_ffmpeg(cmd)
    return str(playlist)


async def frames_to_video(
    frames: list,
    audio_path: str,
    output_path: str,
    fps: float = 25.0,
) -> None:
    """Write a list of BGR numpy frames to an MP4 with the given audio track."""
    import tempfile
    import numpy as np
    import cv2

    if not frames:
        raise ValueError("frames_to_video: empty frame list")

    h, w = frames[0].shape[:2]
    tmp_video = output_path + ".silent.mp4"

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(tmp_video, fourcc, fps, (w, h))
    for frame in frames:
        writer.write(frame if frame.dtype == np.uint8 else (frame * 255).astype(np.uint8))
    writer.release()

    cmd = [
        "ffmpeg", "-y",
        "-i", tmp_video,
        "-i", audio_path,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",
        "-pix_fmt", "yuv420p",
        output_path,
    ]
    _run_ffmpeg(cmd)
    Path(tmp_video).unlink(missing_ok=True)
    logger.info("frames_to_video_done", frames=len(frames), fps=fps, output=output_path)


def _run_ffmpeg(cmd: list[str]) -> None:
    """Run ffmpeg command, raising on failure."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error("ffmpeg_failed", cmd=" ".join(cmd[:4]), stderr=result.stderr[-500:])
        raise RuntimeError(f"FFmpeg failed: {result.stderr[-300:]}")
