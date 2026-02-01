import os
import subprocess
import shutil
import time
from pathlib import Path
from tkinter import messagebox

# ---------------- CONFIG ----------------
AMA_PATH = r"C:\Users\James Kalam\Downloads\AMA_iOS_Tool\AMA_iOS_Tool\AMA_iOS_Tool\AMA_iOS_Tool"
BATCH_FILE = os.path.join(AMA_PATH, "ApplePhone_Log_Capture.bat")
IOS_LOG_DIR = os.path.join(AMA_PATH, "iOS_log")
IPHONE_MOV_DIR = r"C:\iPhone_Captures"

MAX_VIDEO_DELAY = 30  # seconds

class IOSSession:
    def __init__(self):
        self._proc = None
        self.session_start_time = None
        self.session_end_time = None

    # ---------------- CONNECTION ----------------
    def is_connected(self):
        exe = os.path.join(AMA_PATH, "idevice_id.exe")
        try:
            res = subprocess.run([exe, "-l"], capture_output=True, text=True)
            return len(res.stdout.strip()) > 0
        except:
            return False

    # ---------------- START ----------------
    def start(self):
        # Record session start time (log recording start)
        self.session_start_time = time.time()
        # Launch batch file for log capture
        self._proc = subprocess.Popen([BATCH_FILE], cwd=AMA_PATH, creationflags=subprocess.CREATE_NEW_CONSOLE)

    # ---------------- STOP ----------------
    def stop(self):
        self.session_end_time = time.time()
        if self._proc:
            subprocess.run(f"taskkill /F /T /PID {self._proc.pid}", shell=True)

    # ---------------- SAVE ----------------
    def save(self, target_dir: Path):
        target_dir.mkdir(parents=True, exist_ok=True)

        # ---------------- Logs ----------------
        logs = list(Path(IOS_LOG_DIR).glob("*.txt"))
        if logs:
            latest_log = max(logs, key=os.path.getctime)
            shutil.copy2(latest_log, target_dir / "ios_log.txt")
        else:
            messagebox.showwarning("Warning", "No log file found.")

        # ---------------- Videos ----------------
        vids = list(Path(IPHONE_MOV_DIR).glob("*.mov"))

        if not vids:
            messagebox.showwarning("Warning", "No video found in C:\\iPhone_Captures")
            return False, "No MOV video found"

        # Filter videos: only those after session_start_time and within MAX_VIDEO_DELAY
        valid_videos = [
            v for v in vids
            if self.session_start_time and
               self.session_start_time <= v.stat().st_mtime <= self.session_start_time + MAX_VIDEO_DELAY
        ]

        if not valid_videos:
            messagebox.showinfo("Info", "Please start recording the video **after clicking START button**")
            return False, "No valid video found for this session"

        # Pick latest video within session window
        latest_vid = max(valid_videos, key=lambda v: v.stat().st_mtime)
        shutil.copy2(latest_vid, target_dir / "ios_video.mov")

        return True, "iOS Data Exported Successfully"
