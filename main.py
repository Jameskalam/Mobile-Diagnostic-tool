import threading
from pathlib import Path
from tkinter import filedialog, messagebox
import customtkinter as ctk

from android_handler import AndroidSession
from ios_handler import IOSSession
from device_manager import DeviceManager

# ==============================================================================
# WELCOME TO THE COMMAND CENTER (main.py)
# ==============================================================================
# Think of this file as the "Waiter" in a restaurant.
# 1. It greets you (The User Interface).
# 2. It takes your order (Start Recording, Stop Recording).
# 3. It tells the Kitchen (AndroidSession/IOSSession) what to cook.
#
# KEY SECTIONS:
# - SessionTab: Represents ONE table (one phone). It has its own Start/Stop buttons.
# - DiagnosticApp: The entire Restaurant building. It holds all the tables (tabs).
# ==============================================================================

# --- Apple/Premium Aesthetic Constants ---

# --- Apple/Premium Aesthetic Constants ---
BG_COLOR = "#1c1c1e"  # iOS System Background Dark
CARD_COLOR = "#2c2c2e"  # iOS Secondary System Background Dark
ACCENT_BLUE = "#007AFF"  # iOS System Blue
ACCENT_RED = "#FF3B30"  # iOS System Red
ACCENT_GREEN = "#34C759"  # iOS System Green
ACCENT_ORANGE = "#FF9500"  # iOS System Orange
TEXT_WHITE = "#FFFFFF"
TEXT_GREY = "#8E8E93"  # iOS System Gray

FONT_MAIN = ("Segoe UI", 13)
FONT_BOLD = ("Segoe UI", 13, "bold")
FONT_HEADER = ("Segoe UI", 32, "bold")
FONT_SUBHEADER = ("Segoe UI", 12, "bold")


class SessionTab:
    """
    THE TABLE
    This class controls everything for ONE specific phone.
    If you have 3 phones connected, you will have 3 copies of this class running.
    """

    def __init__(self, parent_frame, device_info, close_callback):
        self.parent = parent_frame
        self.device = device_info  # The Menu (Phone Details: ID, Model)
        self.close_callback = close_callback
        self.session = None  # The Order (The active recording job)

        # UI Elements (The Cutlery)
        self.platform_label = None
        self.model_label = None
        self.capture_dropdown = None
        self.preview_checkbox = None
        self.scan_checkbox_var = None  # CTk variable
        self.start_btn = None
        self.stop_btn = None
        self.snapshot_btn = None
        self.save_btn = None
        self.reset_btn = None
        self.info_label = None

        self.build_ui()

    def build_ui(self):
        # --- Info Section ---
        info_frame = ctk.CTkFrame(self.parent, fg_color="transparent")
        info_frame.pack(fill="x", pady=(10, 0))

        # Close Button (X) - Like Browser
        ctk.CTkButton(
            info_frame,
            text="✕",
            width=30,
            height=30,
            fg_color="transparent",
            text_color=TEXT_GREY,
            hover_color="#3a3a3c",
            font=("Arial", 14, "bold"),
            command=self.on_close,
        ).pack(side="right", padx=(5, 0))

        status_color = (
            ACCENT_GREEN
            if self.device["status"] in ("device", "connected")
            else ACCENT_RED
        )
        ctk.CTkLabel(
            info_frame,
            text=f"● {self.device['status'].upper()}",
            text_color=status_color,
            font=("Segoe UI", 10, "bold"),
        ).pack(side="right")

        ctk.CTkLabel(
            info_frame,
            text=f"{self.device['platform']} • {self.device['id']}",
            text_color=ACCENT_BLUE,
            font=FONT_BOLD,
        ).pack(side="left")

        # --- Config Section ---
        config_frame = ctk.CTkFrame(self.parent, fg_color=CARD_COLOR, corner_radius=15)
        config_frame.pack(fill="x", pady=15, padx=5)

        # Capture Mode
        ctk.CTkLabel(
            config_frame, text="Capture Mode", text_color=TEXT_GREY, font=FONT_SUBHEADER
        ).pack(pady=(15, 5))

        modes = ["Video + Log", "Video Only", "Log Only", "Screenshot Only"]
        if self.device["platform"] == "iOS":
            modes = ["Log Only"]  # iOS restrictions

        self.capture_dropdown = ctk.CTkOptionMenu(
            config_frame,
            values=modes,
            width=250,
            fg_color="#3a3a3c",
            button_color="#3a3a3c",
            text_color=TEXT_WHITE,
            command=self.update_ui_state,
        )
        self.capture_dropdown.set(modes[0])
        self.capture_dropdown.pack(pady=(0, 15))

        if self.device["platform"] == "Android":
            self.log_type_var = ctk.StringVar(value="System + App Logs")
            self.log_type_dropdown = ctk.CTkOptionMenu(
                config_frame,
                variable=self.log_type_var,
                values=["System + App Logs", "App Logs Only"],
                width=250,
                fg_color="#3a3a3c",
                button_color="#3a3a3c",
                text_color=TEXT_WHITE,
            )
            self.log_type_dropdown.pack(pady=(0, 15))

        # Preview Checkbox (Android Only)
        if self.device["platform"] == "Android":
            self.scan_checkbox_var = ctk.BooleanVar(value=True)
            self.preview_checkbox = ctk.CTkCheckBox(
                config_frame,
                text="Show Preview Window",
                variable=self.scan_checkbox_var,
                text_color=TEXT_WHITE,
                checkmark_color=TEXT_WHITE,
                fg_color=ACCENT_BLUE,
                hover_color=ACCENT_BLUE,
            )
            self.preview_checkbox.pack(pady=(0, 15))

        # --- Controls Section ---
        self.start_btn = ctk.CTkButton(
            self.parent,
            text="Start Session",
            height=40,
            font=FONT_BOLD,
            fg_color=ACCENT_GREEN,
            hover_color="#2da84a",
            command=self.on_start,
        )
        self.start_btn.pack(pady=5, fill="x", padx=20)

        self.stop_btn = ctk.CTkButton(
            self.parent,
            text="Stop Session",
            height=40,
            font=FONT_BOLD,
            fg_color="#3a3a3c",
            state="disabled",
            hover_color=ACCENT_RED,
            command=self.on_stop,
        )
        self.stop_btn.pack(pady=5, fill="x", padx=20)

        # Extras
        extras_frame = ctk.CTkFrame(self.parent, fg_color="transparent")
        extras_frame.pack(fill="x", pady=10, padx=15)

        self.snapshot_btn = ctk.CTkButton(
            extras_frame,
            text="Screenshot",
            width=100,
            fg_color="#3a3a3c",
            state="disabled",
            command=self.on_snapshot,
        )
        self.snapshot_btn.pack(side="left", padx=5, expand=True)

        self.reset_btn = ctk.CTkButton(
            extras_frame,
            text="Discard",
            width=100,
            fg_color="#3a3a3c",
            state="disabled",
            hover_color=ACCENT_RED,
            command=self.on_reset,
        )
        self.reset_btn.pack(side="left", padx=5, expand=True)

        self.save_btn = ctk.CTkButton(
            self.parent,
            text="Export Data",
            height=40,
            font=FONT_BOLD,
            fg_color="#3a3a3c",
            state="disabled",
            hover_color=ACCENT_BLUE,
            command=self.on_save,
        )
        self.save_btn.pack(pady=10, fill="x", padx=20)

        self.info_label = ctk.CTkLabel(self.parent, text="READY", text_color=TEXT_GREY)
        self.info_label.pack(pady=5)

        self.update_ui_state(self.capture_dropdown.get())

    def update_ui_state(self, mode):
        # Enable/Disable snapshot based on mode logic if needed
        if mode == "Screenshot Only":
            self.start_btn.configure(state="disabled", fg_color="#3a3a3c")
            self.stop_btn.configure(state="disabled", fg_color="#3a3a3c")
            self.snapshot_btn.configure(state="normal", fg_color=ACCENT_ORANGE)
            self.info_label.configure(
                text="READY FOR SCREENSHOTS", text_color=ACCENT_GREEN
            )
            if hasattr(self, "log_type_dropdown"):
                self.log_type_dropdown.configure(state="disabled")
        else:
            # Regular recording modes
            if not self.session:  # If not running
                self.start_btn.configure(state="normal", fg_color=ACCENT_GREEN)
                self.stop_btn.configure(state="disabled", fg_color="#3a3a3c")
                self.snapshot_btn.configure(
                    state="disabled",
                    fg_color="#3a3a3c",
                )
                self.info_label.configure(text="READY", text_color=TEXT_GREY)
                if hasattr(self, "log_type_dropdown"):
                    if mode == "Video Only":
                        self.log_type_dropdown.configure(state="disabled")
                    else:
                        self.log_type_dropdown.configure(state="normal")

    def on_start(self):
        mode = self.capture_dropdown.get()
        show_preview = True
        if self.scan_checkbox_var:
            show_preview = self.scan_checkbox_var.get()

        self.start_btn.configure(state="disabled")
        self.info_label.configure(text="INITIALIZING...", text_color=ACCENT_ORANGE)

        if self.device["platform"] == "iOS":
            # Run countdown on main thread, then start session in background
            self._run_countdown(3, lambda: self._start_session_background(mode, show_preview))
        else:
            self._start_session_background(mode, show_preview)

    def _run_countdown(self, remaining, callback):
        """Non-blocking countdown on the main thread using after()."""
        if remaining > 0:
            self.info_label.configure(
                text=f"Starting in {remaining}...", text_color=ACCENT_ORANGE
            )
            self.parent.after(1000, self._run_countdown, remaining - 1, callback)
        else:
            callback()

    def _start_session_background(self, mode, show_preview):
        def run():
            try:
                if self.device["platform"] == "Android":
                    log_type = (
                        self.log_type_var.get()
                        if hasattr(self, "log_type_var")
                        else "System + App Logs"
                    )
                    self.session = AndroidSession(
                        self.device["id"],
                        capture_mode=mode,
                        show_preview=show_preview,
                        log_type=log_type,
                    )
                else:
                    self.session = IOSSession(self.device["id"])

                if not self.session.is_connected():
                    dev_id = self.device["id"]
                    self.start_btn.after(
                        0,
                        lambda: [
                            messagebox.showerror(
                                "Error", f"Device {dev_id} not accessible!"
                            ),
                            self.start_btn.configure(state="normal"),
                        ],
                    )
                    return

                self.session.start()

                # UI Updates on Main Thread
                self.start_btn.after(
                    0,
                    lambda: [
                        self.stop_btn.configure(state="normal", fg_color=ACCENT_RED),
                        self.snapshot_btn.configure(
                            state="normal"
                            if self.device["platform"] == "Android"
                            else "disabled",
                            fg_color=ACCENT_ORANGE
                            if self.device["platform"] == "Android"
                            else "#3a3a3c",
                        ),
                        self.info_label.configure(
                            text=f"● RECORDING ({mode})", text_color=ACCENT_RED
                        ),
                    ],
                )
            except Exception as e:
                err_msg = str(e)
                self.start_btn.after(
                    0,
                    lambda: [
                        messagebox.showerror("Error", err_msg),
                        self.start_btn.configure(state="normal"),
                    ],
                )

        threading.Thread(target=run, daemon=True).start()

    def on_stop(self):
        if not self.session:
            return
        self.info_label.configure(text="FINALIZING...", text_color=ACCENT_ORANGE)
        self.stop_btn.configure(state="disabled")

        def run():
            self.session.stop()
            self.start_btn.after(
                0,
                lambda: [
                    self.start_btn.configure(state="normal"),
                    self.save_btn.configure(state="normal", fg_color=ACCENT_BLUE),
                    self.reset_btn.configure(state="normal", fg_color=ACCENT_RED),
                    self.info_label.configure(
                        text="SESSION FINISHED", text_color=ACCENT_GREEN
                    ),
                ],
            )

        threading.Thread(target=run, daemon=True).start()

    def on_snapshot(self):
        # Lazy init for Screenshot Only mode
        if self.capture_dropdown.get() == "Screenshot Only" and not self.session:
            if self.device["platform"] == "Android":
                self.session = AndroidSession(self.device["id"], "Screenshot Only")
            else:
                self.session = IOSSession(self.device["id"])

        if self.session and hasattr(self.session, "take_screenshot"):
            self.snapshot_btn.configure(state="disabled")

            def run():
                success, path = self.session.take_screenshot()
                self.snapshot_btn.after(
                    0,
                    lambda: [
                        self.snapshot_btn.configure(state="normal"),
                        self.save_btn.configure(state="normal", fg_color=ACCENT_BLUE),
                        self.reset_btn.configure(state="normal", fg_color=ACCENT_RED),
                        self.info_label.configure(
                            text="SNAPSHOT SAVED", text_color=ACCENT_ORANGE
                        )
                        if success
                        else self.info_label.configure(
                            text="SNAPSHOT FAILED", text_color=ACCENT_RED
                        ),
                    ],
                )
                # Revert text
                self.snapshot_btn.after(
                    2000,
                    lambda: self.info_label.configure(
                        text="READY"
                        if not self.stop_btn.cget("state") == "normal"
                        else "● RECORDING"
                    ),
                )

            threading.Thread(target=run, daemon=True).start()

    def on_save(self):
        folder = filedialog.askdirectory()
        if folder:
            success, msg = self.session.save(Path(folder))
            messagebox.showinfo("Export Result", msg)

    def on_reset(self):
        if self.session:
            self.session.reset()
        self.session = None

        self.save_btn.configure(state="disabled", fg_color="#3a3a3c")
        self.reset_btn.configure(state="disabled", fg_color="#3a3a3c")
        self.info_label.configure(text="SESSION DISCARDED", text_color=ACCENT_ORANGE)

        self.update_ui_state(self.capture_dropdown.get())

    def on_close(self):
        # Stop session if running
        if self.session:
            try:
                self.session.stop()
            except Exception:
                pass
        # Callback to remove tab
        if self.close_callback:
            self.close_callback(self.device["id"])


class DiagnosticApp(ctk.CTk):
    """
    THE RESTAURANT MANAGER
    This is the main window. Its job is to:
    1. Open the doors (START).
    2. Find customers (REFRESH DEVICES).
    3. Seat them at tables (CREATE TABS).
    """

    def __init__(self):
        super().__init__()

        self.title("Mobile Diagnostic Workstation Pro")
        self.geometry("600x850")  # Slightly wider for tabs
        self.configure(fg_color=BG_COLOR)

        self.device_tabs = {}  # id -> SessionTab
        self._placeholder_visible = False

        self.build_ui()
        self.refresh_devices()

    def build_ui(self):
        self.protocol("WM_DELETE_WINDOW", self.on_app_closing)

        # Header
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(pady=20)

        ctk.CTkLabel(
            header_frame, text="Diagnostic", font=FONT_HEADER, text_color=TEXT_WHITE
        ).pack(side="left")
        ctk.CTkLabel(
            header_frame, text=" Pro", font=FONT_HEADER, text_color=ACCENT_BLUE
        ).pack(side="left")

        # Controls Box
        controls_frame = ctk.CTkFrame(self, fg_color="transparent")
        controls_frame.pack(pady=(0, 10))

        # Refresh Button
        self.refresh_btn = ctk.CTkButton(
            controls_frame,
            text="↻ Refresh Devices",
            width=140,
            height=35,
            fg_color="#3a3a3c",
            hover_color="#505050",
            command=self.refresh_devices,
            font=FONT_BOLD,
        )
        self.refresh_btn.pack(side="left", padx=10)

        # Info Guide Button
        self.guide_btn = ctk.CTkButton(
            controls_frame,
            text="📖 How to Use",
            width=140,
            height=35,
            fg_color="#3a3a3c",
            hover_color=ACCENT_BLUE,
            command=self.show_guide,
            font=FONT_BOLD,
        )
        self.guide_btn.pack(side="left", padx=10)

        # Tab View
        self.tab_system = ctk.CTkTabview(
            self,
            width=550,
            height=600,
            corner_radius=20,
            fg_color=CARD_COLOR,
            segmented_button_fg_color="#3a3a3c",
            segmented_button_selected_color=ACCENT_BLUE,
            segmented_button_unselected_color="#3a3a3c",
            text_color=TEXT_WHITE,
        )
        self.tab_system.pack(padx=20, pady=10, fill="both", expand=True)

        # Initial Placeholder
        self.tab_system.add("No Devices")
        ctk.CTkLabel(
            self.tab_system.tab("No Devices"),
            text="No devices connected.\nCheck USB connection and click Refresh.",
            text_color=TEXT_GREY,
        ).pack(expand=True)
        self._placeholder_visible = True

    def show_guide(self):
        guide_window = ctk.CTkToplevel(self)
        guide_window.title("How to Use")
        guide_window.geometry("550x550")
        guide_window.attributes("-topmost", True)
        guide_window.configure(fg_color=BG_COLOR)

        # For CTkToplevel on Windows, taking focus
        guide_window.after(100, guide_window.lift)

        scroll_frame = ctk.CTkScrollableFrame(
            guide_window, fg_color=CARD_COLOR, corner_radius=15
        )
        scroll_frame.pack(fill="both", expand=True, padx=20, pady=20)

        guide_text = (
            "📱 Welcome to Mobile Diagnostic Pro!\n\n"
            "Quick Start Guide:\n\n"
            "1. Connect your device: Plug in your Android or iOS device via USB.\n"
            '2. Refresh: Click the "↻ Refresh Devices" button to detect it.\n'
            "3. Select Mode:\n"
            "   • Video + Log: Records screen & captures system/app logs.\n"
            "   • Log Only: Captures only the raw system logs.\n"
            "   • Screenshot Only: Prep the device to take quick snapshots.\n"
            '4. Start: Click "Start Session". You can stop it at any time.\n'
            '5. Export: After stopping, click "Export Data" to save logs, '
            "videos, and images directly into a folder on your PC.\n\n"
            "Important Notes:\n"
            "• Android: Ensure 'USB Debugging' is enabled in Developer Options.\n"
            "• iOS: Ensure the device is 'Trusted' on your PC. (Due to Apple "
            "restrictions, iOS devices support Logs and Screenshots only, not video).\n"
            "• You can connect and record multiple devices at the exact same time "
            "by using different tabs!"
        )

        ctk.CTkLabel(
            scroll_frame,
            text=guide_text,
            text_color=TEXT_WHITE,
            font=FONT_MAIN,
            justify="left",
            wraplength=450,
        ).pack(anchor="w", expand=True, padx=10, pady=10)

        ctk.CTkButton(
            guide_window,
            text="Got it!",
            width=140,
            height=35,
            fg_color=ACCENT_BLUE,
            font=FONT_BOLD,
            command=guide_window.destroy,
        ).pack(pady=(0, 20))

    def refresh_devices(self):
        self.refresh_btn.configure(state="disabled", text="Scanning...")

        def scan():
            devices = DeviceManager.get_all_devices()
            self.after(0, lambda: self.update_tabs(devices))

        threading.Thread(target=scan, daemon=True).start()

    def update_tabs(self, devices):
        current_ids = set(self.device_tabs.keys())
        new_ids = {d["id"] for d in devices}

        # Remove "No Devices" placeholder if real devices exist
        if new_ids and self._placeholder_visible:
            try:
                self.tab_system.delete("No Devices")
                self._placeholder_visible = False
            except ValueError:
                pass  # Already deleted

        # Add new devices
        for dev in devices:
            if dev["id"] not in current_ids:
                # Truncate label if too long
                label = f"{dev['model']} ({dev['id'][-4:]})"
                self.tab_system.add(label)

                # Initialize Tab Logic in the new frame
                tab_frame = self.tab_system.tab(label)
                # Pass self.close_tab as callback
                self.device_tabs[dev["id"]] = SessionTab(tab_frame, dev, self.close_tab)

        # Handle disconnected devices (Optional)

        if not new_ids and len(self.device_tabs) == 0:
            if not self._placeholder_visible:
                self.tab_system.add("No Devices")
                ctk.CTkLabel(
                    self.tab_system.tab("No Devices"),
                    text="No devices connected.",
                    text_color=TEXT_GREY,
                ).pack(expand=True)
                self._placeholder_visible = True

        self.refresh_btn.configure(state="normal", text="↻ Refresh Devices")

    def close_tab(self, device_id):
        if device_id in self.device_tabs:
            # Determine tab name to delete
            # We reconstruct the label logic used in update_tabs
            dev = self.device_tabs[device_id].device
            label = f"{dev['model']} ({dev['id'][-4:]})"

            # Verify if this tab exists (it might have a slightly different name if we changed logic, safe check)
            try:
                self.tab_system.delete(label)
            except Exception:
                # Fallback: scan tabs if needed, but precise name should work
                pass

            del self.device_tabs[device_id]

            # If no tabs left, show placeholder
            if len(self.device_tabs) == 0:
                if not self._placeholder_visible:
                    self.tab_system.add("No Devices")
                    ctk.CTkLabel(
                        self.tab_system.tab("No Devices"),
                        text="No devices connected.",
                        text_color=TEXT_GREY,
                    ).pack(expand=True)
                    self._placeholder_visible = True

    def on_app_closing(self):
        # Stop all running sessions cleanly when closing application
        for tab in list(self.device_tabs.values()):
            if tab.session:
                try:
                    tab.session.stop()
                except Exception:
                    pass
        self.destroy()


if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")
    app = DiagnosticApp()
    try:
        app.mainloop()
    except KeyboardInterrupt:
        app.on_app_closing()
