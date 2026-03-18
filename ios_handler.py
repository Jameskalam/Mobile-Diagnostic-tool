import os
import subprocess
import shutil
import time
from pathlib import Path

# ==============================================================================
# THE CHEF: iOS (ios_handler.py)
# ==============================================================================
# This file does the cooking for iPhones.
# It's a bit different from Android because iPhones are strict!
# We have to use special tricks (like creating .bat files) to make them talk to us.
# ==============================================================================

# ---------------- CONFIG ----------------
import sys

# Determine base path for portability
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent

TOOLS_DIR = BASE_DIR / "tools"
AMA_PATH = TOOLS_DIR / "ios" / "AMA_iOS_Tool" / "AMA_iOS_Tool"

BATCH_FILE = os.path.join(AMA_PATH, "ApplePhone_Log_Capture.bat")
IOS_LOG_DIR = os.path.join(AMA_PATH, "iOS_Logs")

# Working folder for in-progress captures
WORK_FOLDER = BASE_DIR / "temp_session"


class IOSSession:
    def __init__(self, udid):
        self.udid = udid
        self._proc = None
        self._log_file = None
        self._batch_file = None
        self.current_log_name = None  # Track specific log for this session
        self.log_path = None  # Full path to log

        # Ensure work folder exists
        WORK_FOLDER.mkdir(parents=True, exist_ok=True)

    # ---------------- CONNECTION ----------------
    def is_connected(self):
        """Check if THIS iPhone is connected via USB"""
        exe = os.path.join(AMA_PATH, "idevice_id.exe")
        try:
            res = subprocess.run(
                [exe, "-l"],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            return self.udid in res.stdout
        except Exception as e:
            return False

    def get_device_info(self):
        """Fetches Model, OS Version, and Build via ideviceinfo"""
        info = {
            "Device": "iPhone",
            "OS_Version": "Unknown",
            "Build": "Unknown",
            "Serial": self.udid,
        }
        exe = os.path.join(AMA_PATH, "ideviceinfo.exe")
        try:
            res = subprocess.run(
                [exe, "-u", self.udid],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            output = res.stdout

            # Simple parser for Key: Value
            data = {}
            for line in output.splitlines():
                if ":" in line:
                    key, val = line.split(":", 1)
                    data[key.strip()] = val.strip()

            info["Device"] = data.get("ProductType", "iPhone")
            info["OS_Version"] = f"iOS {data.get('ProductVersion', 'Unknown')}"
            info["Build"] = data.get("BuildVersion", "Unknown")

        except Exception as e:
            pass

        return info

    # ---------------- START ----------------
    def start(self):
        """Start iOS log capture session"""

        # Fetch device info immediately
        self.get_device_info()

        # Generate unique log filename
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        log_filename = f"ios_log_{self.udid[:8]}_{timestamp}.txt"
        self.current_log_name = log_filename
        self.log_path = WORK_FOLDER / log_filename

        # Ensure iOS_Logs directory exists (Legacy, but we use it as intermediate storage)
        os.makedirs(IOS_LOG_DIR, exist_ok=True)

        # Custom batch file written to work folder instead of source directory
        self._batch_file = WORK_FOLDER / f"capture_{self.udid[:8]}.bat"
        with open(self._batch_file, "w") as f:
            f.write("@ECHO OFF\n")
            f.write(f"ECHO Connected iOS Device ID: {self.udid[:8]}...\n")
            f.write("ECHO CAPTURING LOGS...\n")
            f.write(f'idevicesyslog.exe -u {self.udid} >> "{self.log_path}"\n')

        try:
            self._proc = subprocess.Popen(
                [str(self._batch_file)],
                cwd=AMA_PATH,
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        except Exception as e:
            raise RuntimeError(f"Failed to start log capture: {e}")

    def take_screenshot(self):
        """Capture a screenshot from iOS device"""
        try:
            ts = time.strftime("%Y%m%d_%H%M%S")
            filename = f"ios_screenshot_{self.udid[:8]}_{ts}.png"
            path = WORK_FOLDER / filename

            counter = 1
            while path.exists():
                path = (
                    WORK_FOLDER / f"ios_screenshot_{self.udid[:8]}_{ts}_{counter}.png"
                )
                counter += 1

            exe = os.path.join(AMA_PATH, "idevicescreenshot.exe")

            # idevicescreenshot [OPTIONS] FILE
            result = subprocess.run(
                [exe, "-u", self.udid, str(path)],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )

            if result.returncode == 0 and path.exists():
                return True, path
            else:
                return False, None
        except Exception as e:
            return False, None

    # ---------------- STOP ----------------
    def stop(self):
        """Stop iOS log capture session"""
        if self._proc:
            try:
                subprocess.run(
                    f"taskkill /F /T /PID {self._proc.pid}",
                    shell=True,
                    timeout=5,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                pass

            # Grace period for file system to finalize writes
            time.sleep(2)

    # ---------------- SAVE ----------------
    def save(self, target_dir: Path):
        """Save logs and screenshots from the session"""
        target_dir.mkdir(parents=True, exist_ok=True)
        exported = False

        # ---------------- Save Logs ----------------
        if self.log_path and self.log_path.exists():
            self._copy_protected(self.log_path, target_dir)
            exported = True

        # ---------------- Save Screenshots ----------------
        screenshots = list(WORK_FOLDER.glob(f"ios_screenshot_{self.udid[:8]}_*.png"))
        if screenshots:
            for shot in screenshots:
                self._copy_protected(shot, target_dir)
            exported = True

        if exported:
            return True, "iOS Session data exported successfully"
        else:
            return False, "No data captured."

    def _copy_protected(self, source_path: Path, target_dir: Path):
        """Copy file to target_dir with rename if exists to prevent overwrite"""
        if not source_path.exists():
            return None

        destination = target_dir / source_path.name
        counter = 1
        stem = destination.stem
        suffix = destination.suffix

        while destination.exists():
            new_name = f"{stem}_{counter}{suffix}"
            destination = target_dir / new_name
            counter += 1

        shutil.copy2(source_path, destination)
        return destination

    def reset(self):
        """Reset session and delete working files"""
        try:
            if self._proc:
                self.stop()
            # Clean work files for this UDID
            for item in WORK_FOLDER.glob(f"*_{self.udid[:8]}_*"):
                if item.is_file():
                    item.unlink()
            # Clean up the generated batch file
            if self._batch_file and self._batch_file.exists():
                self._batch_file.unlink()
        except Exception as e:
            pass

        self._proc = None
        self._batch_file = None
