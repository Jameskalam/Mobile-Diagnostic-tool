import subprocess
import shutil
import signal
from datetime import datetime
from pathlib import Path

import sys
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

# Working folder for in-progress captures
WORK_FOLDER = BASE_DIR / "temp_session"


class AndroidSession:
    def __init__(
        self,
        serial_id,
        capture_mode="Video + Log",
        show_preview=True,
        log_type="System + App Logs",
    ):
        self.serial_id = serial_id
        self.capture_mode = capture_mode
        self.show_preview = show_preview
        self.log_type = log_type
        self._proc = None
        self._log = None
        self._log_file = None
        self.vid_path = None
        self.log_path = None

        WORK_FOLDER.mkdir(parents=True, exist_ok=True)

    def is_connected(self):
        # Retry logic
        for _ in range(2):
            try:
                res = subprocess.run(
                    [ADB_PATH, "-s", self.serial_id, "get-state"],
                    capture_output=True,
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                if "device" in res.stdout:
                    return True
            except Exception:
                pass
        return False

    def start(self):
        # Fetch device info immediately
        self.device_info = self.get_device_info()

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_serial = self.serial_id.replace(":", "_")  # Handle wireless adb serials

        # Standard MP4 format for media recording
        self.vid_path = WORK_FOLDER / f"android_video_{safe_serial}_{ts}.mp4"
        self.log_path = WORK_FOLDER / f"android_log_{safe_serial}_{ts}.txt"

        # LOG ONLY or BOTH
        if self.capture_mode in ("Video + Log", "Log Only"):
            # Clear log buffer to avoid dumping past logs, which cause large initial sizes
            subprocess.run(
                [ADB_PATH, "-s", self.serial_id, "logcat", "-c"],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            # Execute exact shell command without shell=True for cleaner process tracking
            if getattr(self, "log_type", "System + App Logs") == "App Logs Only":
                active_app = self.device_info.get("Active_App")
                cmd = [ADB_PATH, "-s", self.serial_id, "logcat", "-v", "threadtime"]

                pid = None
                if active_app:
                    try:
                        res = subprocess.run(
                            [
                                ADB_PATH,
                                "-s",
                                self.serial_id,
                                "shell",
                                "pidof",
                                active_app,
                            ],
                            capture_output=True,
                            text=True,
                            creationflags=subprocess.CREATE_NO_WINDOW,
                        )
                        output = res.stdout.strip()
                        if output:
                            pid = output.split()[0]
                    except Exception:
                        pass

                if pid:
                    cmd.append(f"--pid={pid}")
            else:
                cmd = [ADB_PATH, "-s", self.serial_id, "logcat", "-v", "threadtime"]

            self._log_file = open(self.log_path, "w", encoding="utf-8")
            self._log = subprocess.Popen(
                cmd,
                stdout=self._log_file,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW,
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

            self._proc = subprocess.Popen(
                cmd,
                shell=False,  # Better for list args
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.STDOUT,
            )

        # SCREENSHOT ONLY
        if self.capture_mode == "Screenshot Only":
            pass

    def take_screenshot(self):
        """Capture a screenshot and save it to the work folder"""
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_serial = self.serial_id.replace(":", "_")
            filename = f"android_screenshot_{safe_serial}_{ts}.png"
            path = WORK_FOLDER / filename

            counter = 1
            while path.exists():
                path = (
                    WORK_FOLDER / f"android_screenshot_{safe_serial}_{ts}_{counter}.png"
                )
                counter += 1

            # Use subprocess without shell=True to avoid CRLF issues with binary data
            # Capture output is safer than redirecting directly to file if adb prints warnings
            result = subprocess.run(
                [ADB_PATH, "-s", self.serial_id, "exec-out", "screencap", "-p"],
                capture_output=True,
                check=False,  # Don't raise immediately, we want to check stdout
                creationflags=subprocess.CREATE_NO_WINDOW,
            )

            if result.returncode != 0:
                return False, None

            # Check for PNG magic bytes (\x89PNG\r\n\x1a\n)
            png_header = b"\x89PNG\r\n\x1a\n"
            data = result.stdout

            start_index = data.find(png_header)
            if start_index == -1:
                return False, None

            # If header is not at 0, strip leading junk (like adb warnings)
            if start_index > 0:
                data = data[start_index:]

            with open(path, "wb") as f:
                f.write(data)

            return True, path
        except Exception as e:
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

            info["Active_App"] = package_name

        except Exception as e:
            pass

        return info

    def stop(self):
        if self._proc:
            self._proc.send_signal(signal.CTRL_BREAK_EVENT)
            try:
                self._proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait()

        if self._log:
            try:
                self._log.terminate()
                self._log.wait(timeout=5)
            except Exception:
                self._log.kill()

            if hasattr(self, "_log_file") and self._log_file:
                try:
                    self._log_file.close()
                except Exception:
                    pass
                self._log_file = None

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
            and self.vid_path
            and self.vid_path.exists()
        ):
            self._copy_protected(self.vid_path, target_dir)
            exported = True

        # LOG
        if (
            self.capture_mode in ("Video + Log", "Log Only")
            and self.log_path
            and self.log_path.exists()
        ):
            self._copy_protected(self.log_path, target_dir)
            exported = True

        # SCREENSHOTS
        screenshots = list(
            WORK_FOLDER.glob(
                f"android_screenshot_{self.serial_id.replace(':', '_')}_*.png"
            )
        )
        if screenshots:
            for shot in screenshots:
                self._copy_protected(shot, target_dir)
            exported = True

        if not exported:
            return False, "No data captured."

        return True, "Session data exported successfully"

    def reset(self):
        """Reset session and delete working files for this device only"""
        try:
            # Stop any running processes first
            self.stop()

            # Delete only files belonging to this session's serial
            safe_serial = self.serial_id.replace(":", "_")
            if WORK_FOLDER.exists():
                for item in WORK_FOLDER.glob(f"*_{safe_serial}_*"):
                    if item.is_file():
                        item.unlink()
        except Exception as e:
            pass

        self._proc = None
        self._log = None
        self._log_file = None
