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
import os
import re

# ==============================================================================
# THE CHEF: ANDROID (android_handler.py)
# ==============================================================================
# This file does the actual cooking (recording, logging) for Android phones.
# It receives an order (Start Session) from the Waiter (main.py).
# It uses tools like ADB and SCRCPY to get the job done.
# ==============================================================================

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
    def __init__(self, serial_id, capture_mode="Video + Log", show_preview=True):
        self.serial_id = serial_id
        self.capture_mode = capture_mode
        self.show_preview = show_preview
        self._proc = None
        self._log = None
        self.vid_path = None
        self.log_path = None
        self.session_start_time = None
        self.session_end_time = None

        if TEMP_FOLDER.exists():
            # Only clean up if we are sure no other sessions are running?
            # For now, let's allow shared temp folder but maybe we should separate subfolders per session?
            # Implemented: Unique filenames prevent collision, so simple cleanup at start might be risky if multiple sessions start close together.
            # Removing the aggressive cleanup for multi-session safety.
            pass
        TEMP_FOLDER.mkdir(parents=True, exist_ok=True)

    def is_connected(self):
        # Retry logic
        for _ in range(2):
            try:
                res = subprocess.run(
                    f'"{ADB_PATH}" -s {self.serial_id} get-state',
                    capture_output=True,
                    text=True,
                    shell=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                if "device" in res.stdout:
                    return True
            except Exception:
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

        # Fetch and print device info to terminal immediately
        self.get_device_info()

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_serial = self.serial_id.replace(":", "_")  # Handle wireless adb serials

        # Standard MP4 format for media recording
        self.vid_path = TEMP_FOLDER / f"android_video_{safe_serial}_{ts}.mp4"
        self.log_path = TEMP_FOLDER / f"android_log_{safe_serial}_{ts}.txt"

        # LOG ONLY or BOTH
        if self.capture_mode in ("Video + Log", "Log Only"):
            # Execute exact shell command with redirect to match terminal behavior exactly
            cmd = f'"{ADB_PATH}" -s {self.serial_id} logcat -v threadtime > "{self.log_path}"'
            self._log = subprocess.Popen(
                cmd,
                shell=True,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                | subprocess.CREATE_NO_WINDOW,
            )

        # VIDEO ONLY or BOTH
        if self.capture_mode in ("Video + Log", "Video Only"):
            # Construct command
            cmd = [
                SCRCPY_PATH,
                "-s",
                self.serial_id,
                "--window-title",
                f"Android Preview ({self.serial_id})",
                "--record",
                str(self.vid_path),
                "--audio-codec=aac",
                "--audio-bit-rate=128K",
                "-Vverbose",
            ]

            if not self.show_preview:
                cmd.append("--no-window")

            print(f"Starting scrcpy: {' '.join(cmd)}")

            # Capture scrcpy output for debugging audio issues
            self.scrcpy_log_path = TEMP_FOLDER / f"scrcpy_log_{safe_serial}_{ts}.txt"
            self._scrcpy_log_file = open(self.scrcpy_log_path, "w", encoding="utf-8")

            self._proc = subprocess.Popen(
                cmd,
                shell=False,  # Better for list args
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                stdout=self._scrcpy_log_file,
                stderr=subprocess.STDOUT,
            )

        # SCREENSHOT ONLY
        if self.capture_mode == "Screenshot Only":
            print("Session started: Screenshot Only mode")

    def take_screenshot(self):
        """Capture a screenshot and save it to the temp folder"""
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_serial = self.serial_id.replace(":", "_")
            filename = f"android_screenshot_{safe_serial}_{ts}.png"
            path = TEMP_FOLDER / filename

            # Use subprocess without shell=True to avoid CRLF issues with binary data
            # Capture output is safer than redirecting directly to file if adb prints warnings
            result = subprocess.run(
                [ADB_PATH, "-s", self.serial_id, "exec-out", "screencap", "-p"],
                capture_output=True,
                check=False,  # Don't raise immediately, we want to check stdout
                creationflags=subprocess.CREATE_NO_WINDOW,
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

    def get_device_info(self):
        """Fetches Brand, Model, OS Version, Build, Locale, Account, and App Version via ADB"""
        info = {
            "Brand": "Unknown",
            "Device": "Unknown",
            "OS_Version": "Unknown",
            "Build": "Unknown",
            "Locale": "Unknown",
            "Account": "Unknown",
            "App_Version": "N/A",
        }
        print(f"\n🔍 Fetching diagnostics for device {self.serial_id}...", flush=True)
        try:
            # 1. Device Identity (Brand + Model)
            res = subprocess.run(
                [
                    ADB_PATH,
                    "-s",
                    self.serial_id,
                    "shell",
                    "getprop",
                    "ro.product.brand",
                ],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            info["Brand"] = res.stdout.strip().capitalize() or "Unknown"

            res = subprocess.run(
                [
                    ADB_PATH,
                    "-s",
                    self.serial_id,
                    "shell",
                    "getprop",
                    "ro.product.model",
                ],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            info["Device"] = res.stdout.strip() or "Unknown"
            print(
                f"   - Identified Device: {info['Brand']} {info['Device']}", flush=True
            )

            # 2. OS Version (Android + Fire OS check)
            res = subprocess.run(
                [
                    ADB_PATH,
                    "-s",
                    self.serial_id,
                    "shell",
                    "getprop",
                    "ro.build.version.release",
                ],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            android_ver = res.stdout.strip() or "Unknown"

            res = subprocess.run(
                [
                    ADB_PATH,
                    "-s",
                    self.serial_id,
                    "shell",
                    "getprop",
                    "ro.build.version.fireos",
                ],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            fireos_ver = res.stdout.strip()

            if fireos_ver:
                info["OS_Version"] = f"Android {android_ver} (Fire OS {fireos_ver})"
            else:
                info["OS_Version"] = f"Android {android_ver}"

            # 3. Build Number
            res = subprocess.run(
                [
                    ADB_PATH,
                    "-s",
                    self.serial_id,
                    "shell",
                    "getprop",
                    "ro.build.display.id",
                ],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            info["Build"] = res.stdout.strip() or "Unknown"

            # 4. Locale
            res = subprocess.run(
                [
                    ADB_PATH,
                    "-s",
                    self.serial_id,
                    "shell",
                    "getprop",
                    "persist.sys.locale",
                ],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            info["Locale"] = res.stdout.strip() or "Unknown"

            # 5. Account
            res = subprocess.run(
                [ADB_PATH, "-s", self.serial_id, "shell", "dumpsys", "account"],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            accounts = re.findall(
                r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", res.stdout
            )
            if accounts:
                info["Account"] = accounts[0]

            # 6. Active App Detection (More robust using dumpsys window)
            res = subprocess.run(
                [
                    ADB_PATH,
                    "-s",
                    self.serial_id,
                    "shell",
                    "dumpsys",
                    "window",
                    "windows",
                ],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            package_name = None
            for line in res.stdout.splitlines():
                if "mCurrentFocus" in line or "mFocusedApp" in line:
                    match = re.search(r"([a-z0-9_]+\.[a-z0-9_.]+)", line)
                    if match:
                        package_name = match.group(1)
                        if package_name not in (
                            "android",
                            "com.android.systemui",
                            "com.amazon.firelauncher",
                        ):
                            break

            if not package_name:  # Fallback
                res = subprocess.run(
                    [
                        ADB_PATH,
                        "-s",
                        self.serial_id,
                        "shell",
                        "dumpsys",
                        "activity",
                        "recents",
                    ],
                    capture_output=True,
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                for line in res.stdout.splitlines():
                    if "Recent #0" in line:
                        match = re.search(r"([a-zA-Z0-9._]+)/", line)
                        if match:
                            package_name = match.group(1)
                        break

            if package_name:
                res = subprocess.run(
                    [
                        ADB_PATH,
                        "-s",
                        self.serial_id,
                        "shell",
                        "dumpsys",
                        "package",
                        package_name,
                    ],
                    capture_output=True,
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                for line in res.stdout.splitlines():
                    if "versionName=" in line:
                        info["App_Version"] = line.split("=")[-1].strip()
                        break

            print("\n" + "=" * 55, flush=True)
            print("📱 DEVICE DIAGNOSTICS DETECTED", flush=True)
            print(f"   Device:      {info['Brand']} {info['Device']}", flush=True)
            print(f"   OS Version:  {info['OS_Version']}", flush=True)
            print(f"   Build:       {info['Build']}", flush=True)
            print(f"   Locale:      {info['Locale']}", flush=True)
            print(f"   Account:     {info['Account']}", flush=True)
            print(f"   Active App:  {package_name or 'N/A'}", flush=True)
            print(f"   App Version: {info['App_Version']}", flush=True)
            print("=" * 55 + "\n", flush=True)

        except Exception as e:
            print(f"Failed to fetch device info: {e}", flush=True)

        return info

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

        time.sleep(2)

    def _copy_protected(self, source_path: Path, target_dir: Path):
        """Copy file to target_dir with rename if exists to prevent overwrite"""
        if not source_path.exists():
            return None

        destination = target_dir / source_path.name
        counter = 1
        stem = destination.stem
        suffix = destination.suffix

        while destination.exists():
            # If file exists, append counter (e.g. video_1.mp4)
            new_name = f"{stem}_{counter}{suffix}"
            destination = target_dir / new_name
            counter += 1

        shutil.copy2(source_path, destination)
        return destination

    def save(self, target_dir: Path):
        target_dir.mkdir(parents=True, exist_ok=True)
        exported = False

        # VIDEO
        if (
            self.capture_mode in ("Video + Log", "Video Only")
            and self.vid_path.exists()
        ):
            dest_video = self._copy_protected(self.vid_path, target_dir)

            if dest_video:
                # Set Windows file timestamps (creation, access, modification)
                if self.session_start_time and self.session_end_time:
                    self._set_file_times(
                        dest_video, self.session_start_time, self.session_end_time
                    )
                exported = True

        # LOG
        if self.capture_mode in ("Video + Log", "Log Only") and self.log_path.exists():
            dest_log = self._copy_protected(self.log_path, target_dir)

            if dest_log:
                # Set Windows file timestamps (creation, access, modification)
                if self.session_start_time and self.session_end_time:
                    self._set_file_times(
                        dest_log, self.session_start_time, self.session_end_time
                    )
                exported = True

        # SCREENSHOTS
        screenshots = list(
            TEMP_FOLDER.glob(
                f"android_screenshot_{self.serial_id.replace(':', '_')}_*.png"
            )
        )
        if screenshots:
            for shot in screenshots:
                dest_shot = self._copy_protected(shot, target_dir)
                if dest_shot and self.session_start_time and self.session_end_time:
                    self._set_file_times(
                        dest_shot, self.session_start_time, self.session_end_time
                    )
            exported = True

        # Save session time info to a text file
        if self.session_start_time and self.session_end_time:
            session_info_path = target_dir / "session_info.txt"
            duration = self.session_end_time - self.session_start_time

            with open(session_info_path, "w") as f:
                f.write("Session Information")
                f.write("=" * 50 + "")
                f.write(f"Start Time: {time.ctime(self.session_start_time)}")
                f.write(f"End Time: {time.ctime(self.session_end_time)}")
                f.write(
                    f"Duration: {duration:.2f} seconds ({duration / 60:.2f} minutes)"
                )
                f.write(f"Capture Mode: {self.capture_mode}")
                f.write("Timestamp (Unix):")
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
