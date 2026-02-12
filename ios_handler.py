import os
import subprocess
import shutil
import time
import uuid
from pathlib import Path
from tkinter import messagebox, Toplevel, Listbox, Button, Label, SINGLE
import tkinter as tk
import win32com.client

# i have an idea like in broswer where youser can create a n number of tabs by clicking + , can we implement here like that where user can select 1 as android video log and 2 as iOS for log like ....5 tabs alone , if dont want user can easily cut that

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
TEMP_VIDEO_DIR = Path.home() / "Videos" / "iPhone_Temp"

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

    # ---------------- START ----------------
    def start(self, show_instructions=True):
        """Start iOS log capture session with countdown"""

        # Show countdown before starting
        self._show_countdown(COUNTDOWN_SECONDS)

        # Record session start time (after countdown)
        self.session_start_time = time.time()

        # Generate unique log filename with timestamp + UUID to prevent overwrites
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]  # Short UUID
        log_filename = f"IOS_log_{timestamp}_{unique_id}.txt"
        self.current_log_name = log_filename  # Store for saving

        # Ensure iOS_Logs directory exists
        os.makedirs(IOS_LOG_DIR, exist_ok=True)

        # Create a custom batch file with unique log name (visible CMD window)
        # idevicesyslog -u <udid>
        custom_batch = os.path.join(AMA_PATH, f"capture_{unique_id}.bat")
        with open(custom_batch, "w") as f:
            f.write(f"@ECHO OFF\n")
            f.write(f"ECHO Starting iOS Log Capture ({self.udid})...\n")
            f.write(f"ECHO.\n")
            f.write(f"idevicesyslog.exe -u {self.udid} >> iOS_Logs\\{log_filename}\n")

        # Launch custom batch file for log capture
        try:
            self._proc = subprocess.Popen(
                [custom_batch],
                cwd=AMA_PATH,
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
            print(f"Session started at: {time.ctime(self.session_start_time)}")
            print(f"Log file: {log_filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start log capture: {e}")
            self.session_start_time = None

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
        """Save logs from the session (video functionality removed)"""

        if not self.session_start_time or not self.session_end_time:
            messagebox.showerror(
                "Error", "Invalid session: start or stop time not recorded"
            )
            return False, "Invalid session times"

        target_dir.mkdir(parents=True, exist_ok=True)

        # ---------------- Save Logs ----------------
        log_saved = self._save_logs(target_dir)

        if log_saved:
            return True, "iOS Logs Exported Successfully"
        else:
            return False, "Failed to save log files"

    def _save_logs(self, target_dir: Path):
        """Save the current session's log file"""
        try:
            # Use specific log file if we tracked it
            if self.current_log_name:
                source_path = Path(IOS_LOG_DIR) / self.current_log_name
            else:
                # Fallback to latest (legacy behavior)
                logs = list(Path(IOS_LOG_DIR).glob("*.txt"))
                if not logs:
                    messagebox.showwarning("Warning", "No log file found")
                    return False
                source_path = max(logs, key=os.path.getctime)

            if not source_path.exists():
                messagebox.showerror("Error", f"Log file not found: {source_path.name}")
                return False

            # Ensure unique destination filename
            base_name = source_path.stem
            extension = source_path.suffix
            destination = target_dir / source_path.name

            counter = 1
            while destination.exists():
                new_name = f"{base_name}_{counter}{extension}"
                destination = target_dir / new_name
                counter += 1

            print(f"Copying log from: {source_path}")
            print(f"Copying log to: {destination}")

            shutil.copy2(source_path, destination)

            # Verify the file was copied
            if destination.exists():
                print(f"✓ Log saved successfully: {destination.name}")
                print(f"✓ File size: {destination.stat().st_size} bytes")
                # messagebox.showinfo("Success", f"Log exported to:\n{destination}") # Suppress duplicate popup if needed
                return True
            else:
                print(f"✗ File copy failed!")
                return False

        except Exception as e:
            print(f"Error during save: {e}")
            messagebox.showerror("Error", f"Failed to save log: {e}")
            return False

    # ---------------- SESSION INFO ----------------
    def get_session_duration(self):
        """Get session duration in seconds"""
        if self.session_start_time and self.session_end_time:
            return self.session_end_time - self.session_start_time
        return 0

    def reset(self):
        """Reset session state"""
        self.session_start_time = None
        self.session_end_time = None
        self._proc = None
