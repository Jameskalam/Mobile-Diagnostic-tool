import os
import subprocess
import shutil
import time
import signal
from datetime import datetime
from pathlib import Path

SCRCPY_DIR = r"C:\Users\James Kalam\Downloads\scrcpy-win64-v3.3.4\scrcpy-win64-v3.3.4"
ADB_PATH = os.path.join(SCRCPY_DIR, "adb.exe")
SCRCPY_PATH = os.path.join(SCRCPY_DIR, "scrcpy.exe")

TEMP_FOLDER = Path("C:/Amazon_Temp_Diagnostic")

class AndroidSession:
    def __init__(self, capture_mode="Video + Log"):
        self.capture_mode = capture_mode
        self._proc = None
        self._log = None
        self.vid_path = None
        self.log_path = None

        if TEMP_FOLDER.exists():
            try:
                shutil.rmtree(TEMP_FOLDER)
            except:
                pass
        TEMP_FOLDER.mkdir(parents=True, exist_ok=True)

    def is_connected(self):
        try:
            res = subprocess.run(
                f'"{ADB_PATH}" devices',
                capture_output=True,
                text=True,
                shell=True
            )
            return "\tdevice" in res.stdout
        except:
            return False

    def start(self):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        self.vid_path = TEMP_FOLDER / f"android_video_{ts}.mp4"
        self.log_path = TEMP_FOLDER / f"android_log_{ts}.txt"

        # LOG ONLY or BOTH
        if self.capture_mode in ("Video + Log", "Log Only"):
            subprocess.run(f'"{ADB_PATH}" logcat -c', shell=True)
            self._log = subprocess.Popen(
                f'"{ADB_PATH}" logcat -v threadtime > "{self.log_path}"',
                shell=True,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )

        # VIDEO ONLY or BOTH
        if self.capture_mode in ("Video + Log", "Video Only"):
            cmd = (
                f'"{SCRCPY_PATH}" '
                f'--no-playback '
                f'--record="{self.vid_path}" '
                f'--no-audio'
            )
            self._proc = subprocess.Popen(
                cmd,
                shell=True,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )

    def stop(self):
        if self._proc:
            self._proc.send_signal(signal.CTRL_BREAK_EVENT)
            try:
                self._proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass

        if self._log:
            subprocess.run(
                f'taskkill /F /T /PID {self._log.pid}',
                shell=True
            )

        time.sleep(2)

    def save(self, target_dir: Path):
        target_dir.mkdir(parents=True, exist_ok=True)
        exported = False

        if self.capture_mode in ("Video + Log", "Video Only") and self.vid_path.exists():
            shutil.copy2(self.vid_path, target_dir / self.vid_path.name)
            exported = True

        if self.capture_mode in ("Video + Log", "Log Only") and self.log_path.exists():
            shutil.copy2(self.log_path, target_dir / self.log_path.name)
            exported = True

        if not exported:
            return False, "No data captured."

        return True, "Session data exported successfully"
