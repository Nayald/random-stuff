import subprocess
import psutil
import itertools
import argparse
import time
import re
from math import log2
from pathlib import Path
from queue import Queue, Empty
import threading
from threading import Thread

FFMPEG_PATH = Path("C:\\Users\\Xavier\\Documents\\ffmpeg-7.1-full_build\\bin\\ffmpeg.exe")
FFPROBE_PATH = Path("C:\\Users\\Xavier\\Documents\\ffmpeg-7.1-full_build\\bin\\ffprobe.exe")


def parse_sexagesimal_time(time: str) -> float:
    result = 0.
    tokens = time.split(":")
    if len(tokens) > 3:
        print()
        return result
    
    for i, t in enumerate(reversed(tokens)):
        result += float(t) * 60 ** i
        
    return result


def get_duration(media_path: Path) -> float:
    args = [FFPROBE_PATH]
    args += "-v warning -show_entries format=duration -of default=noprint_wrappers=1:nokey=1".split()
    args.append(media_path)
    print(*args)
    return float(subprocess.run(args, capture_output=True, text=True).stdout)


def get_segments(media_path, start_time: float = 0, end_time: float = float("inf"), min_duration: float=5, max_duration: float=float("inf"), scenecut_threshold: float=0) -> list[tuple[float, float]]:
    end_time = min(end_time, get_duration(media_path))
    pts_times = [start_time]
    if scenecut_threshold > 0:
        args = [FFMPEG_PATH]
        args += f"-hide_banner -loglevel warning -ss {start_time} -to {end_time} -i".split()
        args.append(media_path)
        args += "-an -vf".split()
        args.append(f"select='gt(scene,{scenecut_threshold})',metadata=print:file=-")
        args += "-f null -".split()
        print(*args)
        result = subprocess.run(args, shell=False, capture_output=True, text=True, universal_newlines=True)
        if result.returncode != 0:
            print(f"error while getting scene scores with {media_path} -> return code {result.returncode}")
            print(result.stderr)
            exit(-1)
            
        pts_times.extend(float(l.split(":")[-1]) for l in result.stdout.split("\n") if l.startswith("frame"))
    else:
        pts_times.extend(min_duration * i for i in range(1, 1 + int(end_time / min_duration)))
        
    if pts_times[-1] < end_time:
        pts_times.append(end_time)
        
    segments = []
    last = pts_times[0]
    for t in pts_times[1:]:
        if t - last < min_duration:
            continue
        
        while t - last > max_duration + min_duration:
            segments.append((last, max_duration))
            last = round(last + max_duration, 6)
            
        segments.append((last, round(t - last, 6)))
        last = t
        
    if t != last:
        segments[-1] = (segments[-1][0], round(t - segments[-1][0], 6))
    
    return segments


def encode(out_name, start_time, duration, affinity):
    params = [FFMPEG_PATH, *"-hide_banner -loglevel quiet -stats".split(), "-y", "-ss", str(start_time)]
    if duration:
        params.extend(("-t", str(duration)))

    # round(1 + log2(core_count)) almost reproduce automatic level of parallelism (lp) of svtav1
    params.extend(["-i", str(in_name), *f"-an -pix_fmt yuv420p10le -c:v libsvtav1 -preset 6 -svtav1-params keyint=10s:tune=0:crf=45:lp={log2(affinity[1] - affinity[0] + 2):.0f}".split(), str(out_name)])
    print(*params)
    process = subprocess.Popen(params, shell=False, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, universal_newlines=True, creationflags=subprocess.DETACHED_PROCESS)
    psutil.Process(process.pid).cpu_affinity(list(range(affinity[0], affinity[1] + 1)))
    return process


def enqueue_output(out, queue):
    # read the stream until eof is reached
    for line in iter(out.readline, ''):
        queue.put(line)

    out.close()


def concatenate_fragments(out_names: list[Path]):
    concat_file = in_name.with_stem(in_name.stem + "-concat").with_suffix(".txt")
    with open(concat_file, mode="w") as f:
        f.writelines(f"file '{out_name.absolute()}'\n" for out_name in out_names)

    return subprocess.run(f"{FFMPEG_PATH} -hide_banner -loglevel warning -y -f concat -safe 0 -i {concat_file.absolute()} -c copy {concat_file.with_suffix(in_name.suffix).absolute()}".split(),
                            shell=False, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="This script tries to parallel encode a video based on scene changes")
    parser.add_argument("-e", "--executable", default="ffmpeg", help="path to ffmpeg executable (default expect ffmpeg to be in PATH)")
    parser.add_argument("-d", "--min_duration", type=float, default=10, help="fragment minimum duration in seconds (default = 10")
    parser.add_argument("-D", "--max_duration", type=float, default=20, help="fragment minimum duration in seconds (default = 20")
    parser.add_argument("-sct", "--scenecut_threshold", type=float, default=0, help="scene cut threshold (between 0.0 and 1.0, default = 0.4, if 0.0 then equal duration cut)")
    parser.add_argument("-ss", "--start_time", help="start transcoding at specified time (same as ffmpeg)")
    parser.add_argument("-to", "--end_time", help="stop transcoding after specified time is reached (same as ffmpeg)")
    parser.add_argument("-T", "--temp_dir", help="path to directory to store video fragments (default same directory as filename)")
    parser.add_argument("filename", help="the video file to encode")
    parser.add_argument("affinity", help="comma separated range of cpu index, define parallelism (example: 1-4,5-8)")
    options = parser.parse_args()

    in_name = Path(options.filename)
    if not in_name.exists():
        print(options.filename, "isn't a valid file")
        exit(-1)

    affinities = {tuple(map(int, x.split("-"))) if "-" in x else (int(x), int(x)) for x in options.affinity.split(",")}
    concurrency = len(affinities)
    ffmpeg_path = options.executable
    min_duration = max(1., min(options.min_duration, options.max_duration))
    max_duration = max(options.min_duration, options.max_duration)
    scenecut_threshold = max(0., min(options.scenecut_threshold, 1.)) if options.scenecut_threshold else 0.
    start_time = max(0., parse_sexagesimal_time(options.start_time)) if options.start_time else 0.
    end_time = max(start_time, parse_sexagesimal_time(options.end_time)) if options.end_time else float("inf")
    if not options.temp_dir:
        temp_dir = in_name.with_name(in_name.name + "-temp")
    else:
        temp_dir = Path(options.temp_dir)

    temp_dir.mkdir(parents=True, exist_ok=True)

    print("Calculating number of fragments")
    start_times, durations = zip(*get_segments(in_name, start_time, end_time, min_duration, max_duration, scenecut_threshold))
    out_names = [temp_dir / f"{x}.mkv" for x in range(len(start_times))]
    fragments = sorted(zip(out_names, start_times, durations), key=lambda x: (x[2], -x[1]), reverse=True)
    print(f"found {len(start_times)} fragments and will encode up to {len(affinities)} fragments in parallel")
    print(fragments)
    
    current_processes = []
    for out_name, start_time, duration in fragments:
        affinity = affinities.pop()
        print(f"start segment {out_name.name} on CPU cores from {affinity[0]} to {affinity[1]}")
        process = encode(out_name, start_time, duration, affinity)
        queue = Queue()
        thread = Thread(target=enqueue_output, args=(process.stderr, queue))
        thread.start()
        current_processes.append([affinity, time.time(), out_name, process, thread, queue, 0])
        while True:
            fps = 0
            for process_info in tuple(current_processes):
                if process_info[3].poll() is not None:
                    print(
                        f"finish fragment {process_info[2].name} in {round(time.time() - process_info[1], 3)} seconds")
                    process_info[4].join()
                    current_processes.remove(process_info)
                    affinities.add(process_info[0])
                    continue

                line = b""
                try:
                    while line := process_info[5].get_nowait():
                        pass
                except Empty:
                    result = re.search(r"fps=\s*(\d+(?:\.\d+)?)", str(line))
                    if result:
                        process_info[6] = float(result.groups()[0])

            print(f"current speed = {round(sum(process_info[6] for process_info in current_processes), 2)} fps")
            if len(current_processes) < concurrency:
                break
            else:
                time.sleep(1)

    while current_processes:
        fps = 0
        for process_info in tuple(current_processes):
            if process_info[3].poll() is not None:
                print(f"finish fragment {process_info[2].name} in {round(time.time() - process_info[1], 3)} seconds")
                process_info[4].join()
                current_processes.remove(process_info)
                affinities.add(process_info[0])
                continue

            line = b""
            try:
                while line := process_info[5].get_nowait():
                    pass
            except Empty:
                result = re.search(r"fps=\s*(\d+(?:\.\d+)?)", str(line))
                if result:
                    process_info[6] = float(result.groups()[0])

        print(f"current speed = {sum(process_info[6] for process_info in current_processes)} fps")
        time.sleep(1)

    print("concatenate fragments")
    concatenate_fragments(out_names)