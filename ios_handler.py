
import os
import subprocess
import shutil
import time
from pathlib import Path
from tkinter import messagebox, Toplevel, Listbox, Button, Label, SINGLE
import tkinter as tk

# ---------------- CONFIG ----------------
AMA_PATH = r"C:\Users\James Kalam\Downloads\AMA_iOS_Tool\AMA_iOS_Tool\AMA_iOS_Tool\AMA_iOS_Tool"
BATCH_FILE = os.path.join(AMA_PATH, "ApplePhone_Log_Capture.bat")
IOS_LOG_DIR = os.path.join(AMA_PATH, "iOS_log")
IPHONE_MOV_DIR = r"C:\iPhone_Captures"

START_BUFFER = 10  # seconds before session start
END_BUFFER = 10    # seconds after session end
COUNTDOWN_SECONDS = 3  # countdown before starting

class IOSSession:
    def __init__(self):
        self._proc = None
        self.session_start_time = None
        self.session_end_time = None

    # ---------------- CONNECTION ----------------
    def is_connected(self):
        """Check if iPhone is connected via USB"""
        exe = os.path.join(AMA_PATH, "idevice_id.exe")
        try:
            res = subprocess.run([exe, "-l"], capture_output=True, text=True, timeout=5)
            return len(res.stdout.strip()) > 0
        except Exception as e:
            print(f"Connection check failed: {e}")
            return False

    # ---------------- START ----------------
    def start(self, show_instructions=True):
        """Start iOS log capture session with countdown"""
        
        # Show pre-session instructions
        if show_instructions:
            messagebox.showinfo(
                "Important Instructions",
                "Please START VIDEO RECORDING on your iPhone NOW,
"
                "then click OK to begin the session.

"
                "The session will start after a 3-second countdown."
            )
        
        # Countdown before starting
        self._show_countdown(COUNTDOWN_SECONDS)
        
        # Record session start time (after countdown)
        self.session_start_time = time.time()
        
        # Launch batch file for log capture
        try:
            self._proc = subprocess.Popen(
                [BATCH_FILE], 
                cwd=AMA_PATH, 
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
            print(f"Session started at: {time.ctime(self.session_start_time)}")
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
                subprocess.run(f"taskkill /F /T /PID {self._proc.pid}", shell=True, timeout=5)
                print(f"Session ended at: {time.ctime(self.session_end_time)}")
                
                # Grace period for file system to finalize writes
                time.sleep(2)
            except Exception as e:
                print(f"Error stopping process: {e}")
        else:
            messagebox.showwarning("Warning", "No active session to stop")

    # ---------------- SAVE ----------------
    def save(self, target_dir: Path):
        """Save logs and videos from the session"""
        
        if not self.session_start_time or not self.session_end_time:
            messagebox.showerror("Error", "Invalid session: start or stop time not recorded")
            return False, "Invalid session times"
        
        target_dir.mkdir(parents=True, exist_ok=True)
        
        # ---------------- Save Logs ----------------
        log_saved = self._save_logs(target_dir)
        
        # ---------------- Save Videos ----------------
        video_saved, video_msg = self._save_videos(target_dir)
        
        if log_saved and video_saved:
            return True, "iOS Data Exported Successfully"
        elif log_saved:
            return False, f"Log saved but video issue: {video_msg}"
        else:
            return False, "Failed to save session data"

    def _save_logs(self, target_dir: Path):
        """Save the latest log file"""
        try:
            logs = list(Path(IOS_LOG_DIR).glob("*.txt"))
            if not logs:
                messagebox.showwarning("Warning", "No log file found")
                return False
            
            # Get the most recent log file
            latest_log = max(logs, key=os.path.getctime)
            shutil.copy2(latest_log, target_dir / "ios_log.txt")
            print(f"Log saved: {latest_log.name}")
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save log: {e}")
            return False

    def _save_videos(self, target_dir: Path):
        """Save video with improved time window matching"""
        try:
            vids = list(Path(IPHONE_MOV_DIR).glob("*.mov"))
            
            if not vids:
                msg = "No video found in C:\\iPhone_Captures"
                messagebox.showwarning("Warning", msg)
                return False, msg
            
            # Filter videos within session time window (with buffers)
            start_window = self.session_start_time - START_BUFFER
            end_window = self.session_end_time + END_BUFFER
            
            valid_videos = [
                v for v in vids
                if start_window <= v.stat().st_ctime <= end_window
            ]
            
            if not valid_videos:
                msg = (
                    f"No video found within session window.
"
                    f"Session: {time.ctime(self.session_start_time)} to {time.ctime(self.session_end_time)}
"
                    f"Please ensure video recording started BEFORE clicking START button."
                )
                messagebox.showwarning("Warning", msg)
                return False, "No video in session window"
            
            # Handle multiple videos
            if len(valid_videos) > 1:
                selected_video = self._select_video_dialog(valid_videos)
                if not selected_video:
                    return False, "No video selected"
            else:
                selected_video = valid_videos[0]
            
            # Validate video file
            if selected_video.stat().st_size == 0:
                msg = "Selected video file is empty"
                messagebox.showwarning("Warning", msg)
                return False, msg
            
            # Copy video to target directory
            shutil.copy2(selected_video, target_dir / "ios_video.mov")
            print(f"Video saved: {selected_video.name} ({selected_video.stat().st_size / 1024 / 1024:.2f} MB)")
            return True, "Video saved successfully"
            
        except Exception as e:
            msg = f"Failed to save video: {e}"
            messagebox.showerror("Error", msg)
            return False, msg

    def _select_video_dialog(self, videos):
        """Show dialog to select from multiple videos"""
        dialog = Toplevel()
        dialog.title("Select Video")
        dialog.geometry("500x300")
        
        Label(dialog, text="Multiple videos found. Please select one:", font=("Arial", 10)).pack(pady=10)
        
        listbox = Listbox(dialog, selectmode=SINGLE, font=("Arial", 9))
        listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        for v in videos:
            size_mb = v.stat().st_size / 1024 / 1024
            created = time.ctime(v.stat().st_ctime)
            listbox.insert(tk.END, f"{v.name} | {size_mb:.2f} MB | Created: {created}")
        
        selected_video = [None]
        
        def on_select():
            selection = listbox.curselection()
            if selection:
                selected_video[0] = videos[selection[0]]
                dialog.destroy()
        
        Button(dialog, text="Select", command=on_select, width=15).pack(pady=10)
        
        dialog.wait_window()
        return selected_video[0]

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

