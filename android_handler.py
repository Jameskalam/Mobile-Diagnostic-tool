import os
import subprocess
import shutil
import time
import signal
from datetime import datetime
from pathlib import Path
import pywintypes
import win32file
import win32con

import sys

# Determine base path for portability
if getattr(sys, "frozen", False):
    # Running as compiled .exe
    BASE_DIR = Path(sys.executable).parent
else:
    # Running as python script
    BASE_DIR = Path(__file__).parent

# Tools are expected to be in a 'tools' folder next to the app
TOOLS_DIR = BASE_DIR / "tools"
# Updated to match the nested folder structure found in tools/android
SCRCPY_DIR = TOOLS_DIR / "android" / "scrcpy-win64-v3.3.4"
ADB_PATH = str(SCRCPY_DIR / "adb.exe")
SCRCPY_PATH = str(SCRCPY_DIR / "scrcpy.exe")

# Temp folder in the user's home directory to assume write permissions
TEMP_FOLDER = Path.home() / "Documents" / "MobileDiagnosticable_Temp"


class AndroidSession:
    def __init__(self, capture_mode="Video + Log"):
        self.capture_mode = capture_mode
        self._proc = None
        self._log = None
        self._log_file = None
        self.vid_path = None
        self.log_path = None
        self.session_start_time = None
        self.session_end_time = None

        if TEMP_FOLDER.exists():
            try:
                shutil.rmtree(TEMP_FOLDER)
            except:
                pass
        TEMP_FOLDER.mkdir(parents=True, exist_ok=True)

    def is_connected(self):
        # Retry logic to handle cases where ADB daemon is starting up
        for _ in range(2):
            try:
                res = subprocess.run(
                    f'"{ADB_PATH}" devices', capture_output=True, text=True, shell=True
                )
                if "\tdevice" in res.stdout:
                    return True
            except:
                pass
            time.sleep(1)
        return False

    def _set_file_times(self, filepath, start_time, end_time):
        """Set Windows file creation, access, and modification times"""
        try:
            # Convert Unix timestamps to Windows FILETIME
            start_filetime = pywintypes.Time(start_time)
            end_filetime = pywintypes.Time(end_time)

            # Open file handle
            handle = win32file.CreateFile(
                str(filepath),
                win32con.GENERIC_WRITE,
                0,
                None,
                win32con.OPEN_EXISTING,
                0,
                None,
            )

            # Set creation, access, and modification times
            win32file.SetFileTime(handle, start_filetime, start_filetime, end_filetime)
            handle.close()
            return True
        except Exception as e:
            print(f"Failed to set file times: {e}")
            return False

    def start(self):
        # Record session start time
        self.session_start_time = time.time()

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Standard MP4 format for media recording
        self.vid_path = TEMP_FOLDER / f"android_video_{ts}.mp4"
        self.log_path = TEMP_FOLDER / f"android_log_{ts}.txt"

        # LOG ONLY or BOTH
        if self.capture_mode in ("Video + Log", "Log Only"):
            subprocess.run(f'"{ADB_PATH}" logcat -c', shell=True)

            # Open file handle directly for exact ADB output format
            self._log_file = open(self.log_path, "w", encoding="utf-8", buffering=1)

            self._log = subprocess.Popen(
                f'"{ADB_PATH}" logcat -v threadtime',
                shell=True,
                stdout=self._log_file,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )

        # VIDEO ONLY or BOTH
        if self.capture_mode in ("Video + Log", "Video Only"):
            # Always try to capture audio (works on Android 11+)
            # --audio-source=playback captures EVERYTHING (App + System/Accessibility)
            # Enable playback so user can HEAR and SEE what is being recorded
            # This ensures they can verify TalkBack audio is actually active
            # Media & Notification Audio Configuration
            # Uses default audio source (output) which is perfect for music/apps
            cmd = (
                f'"{SCRCPY_PATH}" '
                f'--window-title="Android Diagnostic Preview" '
                f'--record="{self.vid_path}" '
                f"--audio-codec=aac "  # Standard audio for MP4
                f"--audio-bit-rate=128K "  # Standard quality
                f"-Vverbose"
            )
            print("Recording Media/Notification Audio (AAC/MP4)")

            # Capture scrcpy output for debugging audio issues
            self.scrcpy_log_path = TEMP_FOLDER / f"scrcpy_log_{ts}.txt"
            self._scrcpy_log_file = open(self.scrcpy_log_path, "w", encoding="utf-8")

            self._proc = subprocess.Popen(
                cmd,
                shell=True,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                stdout=self._scrcpy_log_file,
                stderr=subprocess.STDOUT,
            )

        # SCREENSHOT ONLY
        # No background processes needed, just the session timer
        if self.capture_mode == "Screenshot Only":
            print("Session started: Screenshot Only mode")

    def take_screenshot(self):
        """Capture a screenshot and save it to the temp folder"""
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"android_screenshot_{ts}.png"
            path = TEMP_FOLDER / filename

            # Use subprocess without shell=True to avoid CRLF issues with binary data
            # Capture output is safer than redirecting directly to file if adb prints warnings
            result = subprocess.run(
                [ADB_PATH, "exec-out", "screencap", "-p"],
                capture_output=True,
                check=False,  # Don't raise immediately, we want to check stdout
            )

            if result.returncode != 0:
                print(f"Screenshot command failed: {result.stderr}")
                return False, None

            # Check for PNG magic bytes (\x89PNG\r\n\x1a\n)
            png_header = b"\x89PNG\r\n\x1a\n"
            data = result.stdout

            start_index = data.find(png_header)
            if start_index == -1:
                print("Screenshot failed: No valid PNG header found in output")
                return False, None

            # If header is not at 0, strip leading junk (like adb warnings)
            if start_index > 0:
                data = data[start_index:]

            with open(path, "wb") as f:
                f.write(data)

            return True, path
        except Exception as e:
            print(f"Screenshot failed: {e}")
            return False, None

    def stop(self):
        # Record session end time
        self.session_end_time = time.time()

        if self._proc:
            self._proc.send_signal(signal.CTRL_BREAK_EVENT)
            try:
                self._proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass

            # Close scrcpy log
            if hasattr(self, "_scrcpy_log_file") and self._scrcpy_log_file:
                self._scrcpy_log_file.close()

        if self._log:
            subprocess.run(
                f"taskkill /F /T /PID {self._log.pid}",
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(1)

            # Close file handle to ensure all data is written
            if self._log_file:
                self._log_file.close()

        time.sleep(2)

    def save(self, target_dir: Path):
        target_dir.mkdir(parents=True, exist_ok=True)
        exported = False

        # VIDEO
        if (
            self.capture_mode in ("Video + Log", "Video Only")
            and self.vid_path.exists()
        ):
            dest_video = target_dir / self.vid_path.name
            shutil.copy2(self.vid_path, dest_video)

            # Set Windows file timestamps (creation, access, modification)
            if self.session_start_time and self.session_end_time:
                self._set_file_times(
                    dest_video, self.session_start_time, self.session_end_time
                )

            exported = True

        # LOG
        if self.capture_mode in ("Video + Log", "Log Only") and self.log_path.exists():
            dest_log = target_dir / self.log_path.name
            shutil.copy2(self.log_path, dest_log)

            # Set Windows file timestamps (creation, access, modification)
            if self.session_start_time and self.session_end_time:
                self._set_file_times(
                    dest_log, self.session_start_time, self.session_end_time
                )

            exported = True

        # SCREENSHOTS
        screenshots = list(TEMP_FOLDER.glob("android_screenshot_*.png"))
        if screenshots:
            for shot in screenshots:
                dest_shot = target_dir / shot.name
                shutil.copy2(shot, dest_shot)
                if self.session_start_time and self.session_end_time:
                    self._set_file_times(
                        dest_shot, self.session_start_time, self.session_end_time
                    )
            exported = True

        # Save session time info to a text file
        if self.session_start_time and self.session_end_time:
            session_info_path = target_dir / "session_info.txt"
            duration = self.session_end_time - self.session_start_time

            with open(session_info_path, "w") as f:
                f.write(f"Session Information")
                f.write(f"=" * 50 + "")
                f.write(f"Start Time: {time.ctime(self.session_start_time)}")
                f.write(f"End Time: {time.ctime(self.session_end_time)}")
                f.write(
                    f"Duration: {duration:.2f} seconds ({duration / 60:.2f} minutes)"
                )
                f.write(f"Capture Mode: {self.capture_mode}")
                f.write(f"Timestamp (Unix):")
                f.write(f"Start: {self.session_start_time}")
                f.write(f"End: {self.session_end_time}")

        if not exported:
            return False, "No data captured."

        return True, "Session data exported successfully"

    def get_session_duration(self):
        """Get session duration in seconds"""
        if self.session_start_time and self.session_end_time:
            return self.session_end_time - self.session_start_time
        return 0

    def reset(self):
        """Reset session and delete temporary files"""
        try:
            # Stop any running processes first
            self.stop()

            # Delete all files in temp folder
            if TEMP_FOLDER.exists():
                for item in TEMP_FOLDER.iterdir():
                    if item.is_file():
                        item.unlink()
        except Exception as e:
            print(f"Error during reset: {e}")

        self.session_start_time = None
        self.session_end_time = None
        self._proc = None
        self._log = None
        self._log_file = None
