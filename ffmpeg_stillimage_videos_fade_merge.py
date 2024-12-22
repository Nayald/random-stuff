from collections import deque
from pathlib import Path
from PIL import Image, ImageOps
import json
import subprocess
import sys

FFMPEG_PATH = "C:\\Users\\Xavier\\Documents\\ffmpeg-7.1-full_build\\bin\\ffmpeg.exe"
FFPROBE_PATH = "C:\\Users\\Xavier\\Documents\\ffmpeg-7.1-full_build\\bin\\ffprobe.exe"
W = 1280
H = 720


def sanitize(media_path: Path, image_path: Path, start=0, length=0) -> tuple[bool, Path]:
    if not media_path.exists() or not image_path.exists():
        return False, Path()
    
    tmp_video_path = tmp_dir / media_path.with_suffix(".mkv").name
    if tmp_video_path.exists():
        print("already exists -> reuse the file")
        return True, tmp_video_path
    
    # not sure ffmpeg compute only once the scaled/croped image, so we do it manually
    tmp_image_path = tmp_dir / image_path.with_suffix(".png").name
    with Image.open(image_path) as image:
        ImageOps.fit(image, (W, H), Image.Resampling.LANCZOS).save(tmp_image_path)
    
    args = [FFMPEG_PATH]
    args += "-v warning -stats -y".split()
    args += "-loop 1 -framerate 24 -i".split()
    args.append(tmp_image_path)
    if start:
        args.append("-ss")
        args.append(str(start))
    
    if length:
        args.append("-t")
        args.append(str(length))
        
    args.append("-i")
    args.append(media_path)
    args += "-map 0:v -c:v libx265 -preset veryfast -x265-params crf=0:lossless=1:log-level=warning".split()
    args += "-map 1:a -c:a flac -compression_level 3 -ar 48000 -af loudnorm".split()
    args.append("-shortest")
    args.append(tmp_video_path)
    #print(" ".join(str(e) for e in args))
    return subprocess.run(args).returncode == 0, tmp_video_path


def get_duration(media_path: Path) -> float:
    args = [FFPROBE_PATH]
    args += "-v warning -show_entries format=duration -of default=noprint_wrappers=1:nokey=1".split()
    args.append(media_path)
    return float(subprocess.run(args, capture_output=True).stdout)
    

def fade_merge(video_paths: list[Path], duration=.5) -> bool:
    if not video_paths:
        return True
    
    args = args = [FFMPEG_PATH]
    args += "-v warning -stats -y".split()
    for video_path in video_paths:
        args.append("-i")
        args.append(video_path)
        
    args.append("-filter_complex")
    filter_complex = [f"[0:v]fade=t=in:st=0:d={duration}[v0];[0:a]afade=t=in:st=0:d={duration}[a0];"]
    offset = get_duration(video_paths[0]) - duration
    i = 0
    for i in range(1, len(video_paths)):
        filter_complex.append(f"[v{i - 1}][{i}:v]xfade=transition=fade:duration={duration}:offset={offset}[v{i}];")
        filter_complex.append(f"[a{i - 1}][{i}:a]acrossfade=d={duration}[a{i}];")
        offset += get_duration(video_paths[i]) - duration
        
    filter_complex.append(f"[v{i}]fade=t=out:st={offset}:d={duration}[v];")
    filter_complex.append(f"[a{i}]afade=t=out:st={offset}:d={duration}[a]")
    args.append("".join(filter_complex))
    args += "-map [v] -c:v libx264 -preset fast -tune stillimage -crf 18".split()
    args += "-map [a] -c:a aac -b:a 320k".split()
    args.append(root_dir / "merged.mp4")
    #print(" ".join(str(e) for e in args))
    return subprocess.run(args).returncode == 0


def fade_merge2(video_paths: list[Path], duration=.5) -> bool:
    def helper(a: Path, b: Path, output_path: Path) -> bool:
        args = args = [FFMPEG_PATH]
        args += "-v warning -stats -y".split()
        args.append("-i")
        args.append(a)
        args.append("-i")
        args.append(b)
        args.append("-filter_complex")
        args.append(f"[0:v][1:v]xfade=transition=fade:duration={duration}:offset={get_duration(a) - duration}[v];[0:a][1:a]acrossfade=d={duration}[a]")
        args += "-map [v] -c:v libx265 -preset veryfast -x265-params crf=0:lossless=1:log-level=warning".split()
        args += "-map [a] -c:a flac -compression_level 3".split()
        args.append(output_path)
        return subprocess.run(args).returncode == 0
    
    if not video_paths:
        return True
    
    n = max(0, len(video_paths) - 3)
    print("need", n, "intermediate merge(s)")
    segments = deque()
    for i, (a, b) in enumerate(zip(*[iter(video_paths[1:-1])] * 2), start=1):
        print("step", i, '/', n)
        if helper(a, b, out := tmp_dir / f"{i}.mkv"):
            segments.append(out)
        else:
            print("Failed to merge", a, "and", b)
            out.unlink(missing_ok=True)
            return False
          
    while len(segments) > 1:
        print("step", i := i + 1, '/', n)
        if helper(a := segments.popleft(), b := segments.popleft(), out := tmp_dir / f"{i}.mkv"):
            segments.append(out)
            a.unlink(missing_ok=True)
            b.unlink(missing_ok=True)
        else:
            print("Failed to merge", a, "and", b)
            out.unlink(missing_ok=True)
            a.unlink(missing_ok=True)
            b.unlink(missing_ok=True)
            for path in segments:
                path.unlink(missing_ok=True)
                
            return False
    
    final_segments = [video_paths[0]]
    final_segments.extend(segments)
    if len(video_paths) > 1:
        final_segments.append(video_paths[-1])
        
    print("final merge")
    result = fade_merge(final_segments, duration)
    while segments:
        segments.popleft().unlink(missing_ok=True)
        
    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:", sys.argv[0], "file_path")
        exit(-1)

    metadatafile = Path(sys.argv[1])
    if not metadatafile.exists():
        print("metadata file not found")
        exit(-1)
        
    root_dir = metadatafile.parent
    tmp_dir = root_dir / "tmp"
    Path(tmp_dir).mkdir(parents=True, exist_ok=True)
    with open(metadatafile, encoding="utf8") as f:
        # expected format:
        # [
        #   {
        #       "media_path": a path as string,
        #       "image_path": a path as string,
        #       "start": optional field as number or string understandable by ffmpeg,
        #       "length": optional field as number or string understandable by ffmpeg
        #   }, ...
        # ]
        metadatas = json.load(f)
    
    print(len(metadatas), "media to sanitize")
    tmp_video_paths = []
    for i, metadata in enumerate(metadatas, start=1):
        media_path = Path(metadata["media_path"])
        print("[", i, "/", len(metadatas), "] working on", p if len(p := str(media_path)) <= 50 else p[:25] + "..." + p[-25:])
        success, tmp_video_path = sanitize(media_path, Path(metadata["image_path"]), metadata.get("start", 0), metadata.get("length", 0))
        if success:
            tmp_video_paths.append(tmp_video_path)
        else:
            print("failed to sanitize", tmp_video_path)
            tmp_video_path.unlink(missing_ok=True)
        
    if len(tmp_video_paths) < len(metadatas):
        exit(-1)
    
    print("merging the videos")
    # ffmpeg uses too much ram if a lot of input videos are provided. In this case,
    # it is better to use the second method that split the encoding in multiple subtasks,
    # it takes more time but keep the ram usage small
    if fade_merge2(tmp_video_paths):
        print("all done, clean up")
        for path in tmp_dir.iterdir():
            path.unlink(missing_ok=True)

        tmp_dir.rmdir()
    
