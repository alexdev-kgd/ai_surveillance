import os
import subprocess
from concurrent.futures import ProcessPoolExecutor

input_root = "../dataset"   # root directory with train/val subfolders
output_root = "../dataset_clean"

def convert_video(task):
    in_path, out_path = task
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    # ffmpeg command: overwrite output, suppress logs
    cmd = [
        "ffmpeg",
        "-y",  # overwrite if exists
        "-i", input_path,
        "-vf", "scale=224:224,fps=30",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        output_path
    ]
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        print("Converted:", in_path, "->", out_path)
    except Exception as e:
        print("Failed:", in_path, e)

def collect_videos():
    tasks = []
    for root, _, files in os.walk(input_root):
        for f in files:
            if f.lower().endswith((".mp4", ".avi", ".mov", ".mkv")):
                in_path = os.path.join(root, f)
                rel_path = os.path.relpath(in_path, input_root)
                out_path = os.path.join(output_root, os.path.splitext(rel_path)[0] + ".mp4")
                tasks.append((in_path, out_path))
    return tasks

if __name__ == "__main__":
    videos = collect_videos()
    print(f"Found {len(videos)} videos to convert.")

    with ProcessPoolExecutor(max_workers=8) as ex:
        ex.map(convert_video, videos)