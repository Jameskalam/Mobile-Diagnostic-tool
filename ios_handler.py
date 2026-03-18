import os
import subprocess
import shutil
import time
from pathlib import Path
from tkinter import messagebox, Toplevel, Label

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
# Temp folder in the user's home directory to assume write permissions
TEMP_FOLDER = Path.home() / "Documents" / "MobileDiagnosticable_Temp"

START_BUFFER = 10  # seconds before session start
END_BUFFER = 10  # seconds after session end
COUNTDOWN_SECONDS = 3  # countdown before starting


class IOSSession:
    def __init__(self, udid):
        self.udid = udid
        self._proc = None
        self._log_file = None
        self.session_start_time = None
        self.session_end_time = None
        self.current_log_name = None  # Track specific log for this session
        self.log_path = None  # Full path to temp log

        # Ensure temp folder exists
        TEMP_FOLDER.mkdir(parents=True, exist_ok=True)

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
            print(f"Connection check failed: {e}")
            return False

    def _set_file_times(self, filepath, start_time, end_time):
        """Set Windows file creation, access, and modification times (using powershell for simplicity/no win32 requirement here if not already imported)"""
        # Wait, I see win32file imported in android_handler, but not here.
        # Actually, let's look at ios_handler imports.
        # It has win32com.client but not win32file.
        # I'll use powershell or sub-process to avoid adding more deps if possible,
        # or I can just import win32file/win32con if they are available.
        # Let's check requirements.txt later. For now, let's use a robust way.
        try:
            import pywintypes
            import win32file
            import win32con

            start_filetime = pywintypes.Time(start_time)
            end_filetime = pywintypes.Time(end_time)

            handle = win32file.CreateFile(
                str(filepath),
                win32con.GENERIC_WRITE,
                0,
                None,
                win32con.OPEN_EXISTING,
                0,
                None,
            )
            win32file.SetFileTime(handle, start_filetime, start_filetime, end_filetime)
            handle.close()
            return True
        except Exception as e:
            print(f"Failed to set file times: {e}")
            return False

    def get_device_info(self):
        """Fetches Model, OS Version, and Build via ideviceinfo"""
        info = {
            "Device": "iPhone",
            "OS_Version": "Unknown",
            "Build": "Unknown",
            "Serial": self.udid,
        }
        print(f"\n🔍 Fetching diagnostics for iOS device {self.udid}...", flush=True)
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

            # Try to get human readable name if possible (mapping common types)
            # For brevity, we'll just use ProductType for now or keep it as is.

            print("\n" + "=" * 55, flush=True)
            print("📱 iOS DEVICE DIAGNOSTICS DETECTED", flush=True)
            print(f"   Device:      {info['Device']}", flush=True)
            print(f"   OS Version:  {info['OS_Version']}", flush=True)
            print(f"   Build:       {info['Build']}", flush=True)
            print(f"   UDID:        {info['Serial']}", flush=True)
            print("=" * 55 + "\n", flush=True)
        except Exception as e:
            print(f"Failed to fetch device info: {e}")

        return info

    # ---------------- START ----------------
    def start(self, show_instructions=True):
        """Start iOS log capture session with countdown"""

        # Show countdown before starting
        self._show_countdown(COUNTDOWN_SECONDS)

        # Record session start time (after countdown)
        self.session_start_time = time.time()

        # Fetch device info immediately
        self.get_device_info()

        # Generate unique log filename
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        log_filename = f"ios_log_{self.udid[:8]}_{timestamp}.txt"
        self.current_log_name = log_filename
        self.log_path = TEMP_FOLDER / log_filename

        # Ensure iOS_Logs directory exists (Legacy, but we use it as intermediate storage)
        os.makedirs(IOS_LOG_DIR, exist_ok=True)

        # Capture directly to temp folder if possible, or use batch redirect
        custom_batch = os.path.join(AMA_PATH, f"capture_{self.udid[:8]}.bat")
        with open(custom_batch, "w") as f:
            f.write(f"@ECHO OFF\n")
            f.write(f"ECHO Starting iOS Log Capture ({self.udid})...\n")
            f.write("ECHO.\n")
            # Redirect to user temp folder
            f.write(f'idevicesyslog.exe -u {self.udid} >> "{self.log_path}"\n')

        # Launch custom batch file for log capture
        try:
            self._proc = subprocess.Popen(
                [custom_batch],
                cwd=AMA_PATH,
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
            print(f"Session started: {log_filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start log capture: {e}")
            self.session_start_time = None

    def take_screenshot(self):
        """Capture a screenshot from iOS device"""
        try:
            ts = time.strftime("%Y%m%d_%H%M%S")
            filename = f"ios_screenshot_{self.udid[:8]}_{ts}.png"
            path = TEMP_FOLDER / filename

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
                print(f"Screenshot failed: {result.stderr}")
                return False, None
        except Exception as e:
            print(f"Screenshot error: {e}")
            return False, None

    def _show_countdown(self, seconds):
        """Display countdown window"""
        countdown_window = Toplevel()
        countdown_window.title("Starting Session")
        countdown_window.geometry("300x100")
        countdown_window.resizable(False, False)

        label = Label(countdown_window, text="", font=("Arial", 24))
        label.pack(expand=True)

        for i in range(seconds, 0, -1):
            label.config(text=f"Starting in {i}...")
            countdown_window.update()
            time.sleep(1)

        countdown_window.destroy()

    # ---------------- STOP ----------------
    def stop(self):
        """Stop iOS log capture session"""
        self.session_end_time = time.time()

        if self._proc:
            try:
                subprocess.run(
                    f"taskkill /F /T /PID {self._proc.pid}", shell=True, timeout=5
                )
                print(f"Session ended at: {time.ctime(self.session_end_time)}")

                # Close log file to ensure all data is written
                if self._log_file:
                    self._log_file.close()
                    self._log_file = None

                # Grace period for file system to finalize writes
                time.sleep(2)
            except Exception as e:
                print(f"Error stopping process: {e}")
        else:
            messagebox.showwarning("Warning", "No active session to stop")

    # ---------------- SAVE ----------------
    def save(self, target_dir: Path):
        """Save logs and screenshots from the session"""
        if not self.session_start_time or not self.session_end_time:
            return False, "Invalid session times"

        target_dir.mkdir(parents=True, exist_ok=True)
        exported = False

        # ---------------- Save Logs ----------------
        if self.log_path and self.log_path.exists():
            dest_log = self._copy_protected(self.log_path, target_dir)
            if dest_log:
                self._set_file_times(
                    dest_log, self.session_start_time, self.session_end_time
                )
                exported = True

        # ---------------- Save Screenshots ----------------
        screenshots = list(TEMP_FOLDER.glob(f"ios_screenshot_{self.udid[:8]}_*.png"))
        if screenshots:
            for shot in screenshots:
                dest_shot = self._copy_protected(shot, target_dir)
                if dest_shot:
                    self._set_file_times(
                        dest_shot, self.session_start_time, self.session_end_time
                    )
            exported = True

        # ---------------- Session Info ----------------
        if self.session_start_time and self.session_end_time:
            session_info_path = target_dir / "session_info.txt"
            duration = self.session_end_time - self.session_start_time

            with open(session_info_path, "w") as f:
                f.write("iOS Session Information\n")
                f.write("=" * 50 + "\n")
                f.write(f"Start Time: {time.ctime(self.session_start_time)}\n")
                f.write(f"End Time: {time.ctime(self.session_end_time)}\n")
                f.write(f"Duration: {duration:.2f} seconds\n")
                f.write(f"Device UDID: {self.udid}\n")
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

    # Removed _save_logs as it's replaced by logic in save()

    # ---------------- SESSION INFO ----------------
    def get_session_duration(self):
        """Get session duration in seconds"""
        if self.session_start_time and self.session_end_time:
            return self.session_end_time - self.session_start_time
        return 0

    def reset(self):
        """Reset session and delete temporary files"""
        try:
            self.stop()
            # Clean temp files for this UDID
            for item in TEMP_FOLDER.glob(f"*_{self.udid[:8]}_*"):
                if item.is_file():
                    item.unlink()
        except Exception as e:
            print(f"Error during reset: {e}")

        self.session_start_time = None
        self.session_end_time = None
        self._proc = None
