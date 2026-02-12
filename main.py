import threading
from pathlib import Path
from tkinter import filedialog, messagebox
import customtkinter as ctk

from android_handler import AndroidSession
from ios_handler import IOSSession

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


def main():
    state = {"session": None}

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")

    app = ctk.CTk()
    app.title("Mobile Diagnostic Tool")
    app.geometry("480x800")
    app.resizable(False, False)
    app.configure(fg_color=BG_COLOR)

    # ---------------- INFO ----------------
    def show_info(event):
        messagebox.showinfo(
            "AMQE Tool", "Mobile Diagnostic Workstation\nVersion 2.2 (Premium UI)"
        )

    # ---------------- START ----------------
    def on_start():
        start_btn.configure(state="disabled")

        platform = platform_dropdown.get()
        capture_mode = capture_dropdown.get()

        info_label.configure(
            text=f"INITIALIZING {platform}...", text_color=ACCENT_ORANGE
        )

        def run():
            # ---------- iOS restrictions ----------
            if platform == "iOS":
                # iOS cannot start video only
                if capture_mode == "Video Only":
                    app.after(
                        0,
                        lambda: messagebox.showinfo(
                            "Info",
                            "iOS cannot start video automatically.\nPlease select 'Log Only' or 'Both'.",
                        ),
                    )
                    app.after(0, lambda: start_btn.configure(state="normal"))
                    return

                state["session"] = IOSSession()

                # Check iOS connection
                if not state["session"].is_connected():
                    app.after(
                        0,
                        lambda: [
                            messagebox.showerror("Error", "iOS device not found!"),
                            start_btn.configure(state="normal"),
                            stop_btn.configure(state="disabled"),
                            save_btn.configure(state="disabled"),
                            info_label.configure(
                                text="SYSTEM READY", text_color=TEXT_GREY
                            ),
                        ],
                    )
                    return

                # Start log capture
                state["session"].start()
                app.after(
                    0,
                    lambda: [
                        stop_btn.configure(state="normal"),
                        info_label.configure(
                            text="● LOG RECORDING iOS", text_color=ACCENT_RED
                        ),
                    ],
                )
                return

            # ---------- Android ----------
            state["session"] = AndroidSession(capture_mode)
            if not state["session"].is_connected():
                app.after(
                    0,
                    lambda: [
                        messagebox.showerror("Error", "Android device not found!"),
                        start_btn.configure(state="normal"),
                        stop_btn.configure(state="disabled"),
                        save_btn.configure(state="disabled"),
                        reset_btn.configure(state="disabled"),
                        info_label.configure(text="SYSTEM READY", text_color=TEXT_GREY),
                    ],
                )
                return

            state["session"].start()

            app.after(
                0,
                lambda: [
                    stop_btn.configure(state="normal"),
                    info_label.configure(
                        text=f"● RECORDING Android ({capture_mode})",
                        text_color=ACCENT_RED,
                    ),
                ],
            )

        threading.Thread(target=run, daemon=True).start()

    # ---------------- STOP ----------------
    def on_stop():
        if not state["session"]:
            return

        info_label.configure(text="FINALIZING SESSION...", text_color=ACCENT_ORANGE)

        def run():
            state["session"].stop()
            app.after(
                0,
                lambda: [
                    start_btn.configure(state="normal"),
                    stop_btn.configure(state="disabled"),
                    save_btn.configure(state="normal"),
                    reset_btn.configure(state="normal"),
                    info_label.configure(
                        text="STOPPED – READY TO EXPORT", text_color=ACCENT_GREEN
                    ),
                ],
            )

        threading.Thread(target=run, daemon=True).start()

    # ---------------- SAVE ----------------
    def on_save():
        folder = filedialog.askdirectory()
        if folder:
            success, msg = state["session"].save(Path(folder))
            messagebox.showinfo("Export Result", msg)

    # ---------------- HEADER ----------------
    # Minimalist Header
    ctk.CTkLabel(app, text="Diagnostic", font=FONT_HEADER, text_color=TEXT_WHITE).pack(
        pady=(40, 5)
    )

    ctk.CTkLabel(
        app,
        text="Workstation Pro",
        font=("Segoe UI", 16),
        text_color=ACCENT_BLUE,
    ).pack(pady=(0, 30))

    # ---------------- CARD ----------------
    card = ctk.CTkFrame(app, fg_color=CARD_COLOR, corner_radius=20)
    card.pack(padx=20, pady=10, fill="both", expand=True)

    # Platform selector
    ctk.CTkLabel(
        card, text="Target Platform", font=FONT_SUBHEADER, text_color=TEXT_GREY
    ).pack(pady=(25, 8))
    platform_dropdown = ctk.CTkOptionMenu(
        card,
        values=["Android", "iOS"],
        width=280,
        height=40,
        fg_color="#3a3a3c",
        button_color="#3a3a3c",
        button_hover_color="#48484a",
        text_color=TEXT_WHITE,
        dropdown_fg_color=CARD_COLOR,
        font=FONT_MAIN,
    )
    platform_dropdown.set("Android")
    platform_dropdown.pack(pady=(0, 20))

    # Capture selector
    ctk.CTkLabel(
        card, text="Capture Mode", font=FONT_SUBHEADER, text_color=TEXT_GREY
    ).pack(pady=(10, 8))
    capture_dropdown = ctk.CTkOptionMenu(
        card,
        values=["Video + Log", "Video Only", "Log Only", "Screenshot Only"],
        width=280,
        height=40,
        fg_color="#3a3a3c",
        button_color="#3a3a3c",
        button_hover_color="#48484a",
        text_color=TEXT_WHITE,
        dropdown_fg_color=CARD_COLOR,
        font=FONT_MAIN,
    )
    capture_dropdown.set("Video + Log")
    capture_dropdown.pack(pady=(0, 30))

    # GUI State Updater based on Mode
    def update_ui_for_mode(mode):
        if mode == "Screenshot Only":
            start_btn.configure(state="disabled", fg_color="#3a3a3c")
            stop_btn.configure(state="disabled", fg_color="#3a3a3c")
            snapshot_btn.configure(state="normal", fg_color=ACCENT_ORANGE)
            save_btn.configure(state="disabled", fg_color="#3a3a3c")
            reset_btn.configure(state="disabled", fg_color="#3a3a3c")
            info_label.configure(text="READY FOR SCREENSHOTS", text_color=ACCENT_GREEN)
        else:
            start_btn.configure(state="normal", fg_color=ACCENT_GREEN)
            stop_btn.configure(state="disabled", fg_color="#3a3a3c")
            snapshot_btn.configure(state="disabled", fg_color="#3a3a3c")
            save_btn.configure(state="disabled", fg_color="#3a3a3c")
            reset_btn.configure(state="disabled", fg_color="#3a3a3c")
            info_label.configure(text="SYSTEM READY", text_color=TEXT_GREY)

    # Disable "Video Only" option when iOS is selected
    def update_capture_options(platform):
        if platform == "iOS":
            capture_dropdown.configure(values=["Log Only", "Video + Log"])
            capture_dropdown.set("Log Only")
        else:
            capture_dropdown.configure(
                values=["Video + Log", "Video Only", "Log Only", "Screenshot Only"]
            )
            capture_dropdown.set("Video + Log")

        # Trigger UI update for the new default
        update_ui_for_mode(capture_dropdown.get())

    platform_dropdown.configure(command=update_capture_options)
    capture_dropdown.configure(command=update_ui_for_mode)

    # Buttons
    start_btn = ctk.CTkButton(
        card,
        text="Start Session",
        height=45,
        width=280,
        font=FONT_BOLD,
        fg_color=ACCENT_GREEN,
        hover_color="#2da84a",
        corner_radius=12,
        command=on_start,
    )
    start_btn.pack(pady=8)

    stop_btn = ctk.CTkButton(
        card,
        text="Stop Session",
        height=45,
        width=280,
        font=FONT_BOLD,
        fg_color="#3a3a3c",  # Disabled state look initially
        hover_color=ACCENT_RED,
        corner_radius=12,
        state="disabled",
        command=on_stop,
    )
    stop_btn.pack(pady=8)

    # ---------------- SNAPSHOT ----------------
    def on_snapshot():
        # Auto-initialize session if not running (Lazy Start for Screenshot Only)
        if not state["session"]:
            if capture_dropdown.get() == "Screenshot Only":
                platform = platform_dropdown.get()
                if platform == "Android":
                    state["session"] = AndroidSession("Screenshot Only")
                    if not state["session"].is_connected():
                        messagebox.showerror("Error", "Android device not found!")
                        state["session"] = None
                        return
                    state["session"].start()
                    # Allow Reset now that we have a session
                    reset_btn.configure(state="normal", fg_color=ACCENT_RED)
                else:
                    return  # iOS not fully supported for screenshot only yet

        if not state["session"] or not hasattr(state["session"], "take_screenshot"):
            return

        # Disable button during countdown
        snapshot_btn.configure(state="disabled", fg_color="#3a3a3c")

        def execute_capture():
            success, path = state["session"].take_screenshot()

            # Re-enable button
            snapshot_btn.configure(state="normal", fg_color=ACCENT_ORANGE)

            if success:
                # Flash confirmation or small toast
                info_label.configure(
                    text=f"SNAPSHOT SAVED: {path.name}", text_color=ACCENT_ORANGE
                )

                # Enable Export since we have data now
                save_btn.configure(state="normal", fg_color=ACCENT_BLUE)
                reset_btn.configure(state="normal", fg_color=ACCENT_RED)

                # Revert text after 2 seconds
                mode_text = capture_dropdown.get()
                status_text = (
                    "● READY FOR SCREENSHOTS"
                    if mode_text == "Screenshot Only"
                    else f"● RECORDING Android ({mode_text})"
                )

                app.after(
                    2000,
                    lambda: info_label.configure(
                        text=status_text, text_color=ACCENT_RED
                    ),
                )
            else:
                messagebox.showerror("Error", "Screenshot failed")
                info_label.configure(text="SNAPSHOT FAILED", text_color=ACCENT_RED)

        def countdown(count):
            if count > 0:
                info_label.configure(
                    text=f"CAPTURING IN {count}...", text_color=ACCENT_ORANGE
                )
                app.after(1000, lambda: countdown(count - 1))
            else:
                info_label.configure(text="CAPTURING...", text_color=ACCENT_RED)
                app.after(100, execute_capture)

        # Start countdown
        countdown(3)

    snapshot_btn = ctk.CTkButton(
        card,
        text="Capture Screenshot",
        height=45,
        width=280,
        font=FONT_BOLD,
        fg_color="#3a3a3c",
        hover_color=ACCENT_ORANGE,
        corner_radius=12,
        state="disabled",
        command=on_snapshot,
    )
    snapshot_btn.pack(pady=8)

    save_btn = ctk.CTkButton(
        card,
        text="Export Data",
        height=45,
        width=280,
        font=FONT_BOLD,
        fg_color="#3a3a3c",
        hover_color=ACCENT_BLUE,
        corner_radius=12,
        state="disabled",
        command=on_save,
    )
    save_btn.pack(pady=(25, 8))

    # ---------------- RESET ----------------
    def on_reset():
        if state["session"]:
            state["session"].reset()  # Clean up temp files

        # Reset UI to initial state based on current mode
        update_ui_for_mode(capture_dropdown.get())

        info_label.configure(text="SESSION DISCARDED", text_color=ACCENT_ORANGE)
        app.after(
            2000,
            lambda: update_ui_for_mode(capture_dropdown.get()),
        )

    reset_btn = ctk.CTkButton(
        card,
        text="Discard Session",
        height=45,
        width=280,
        font=FONT_BOLD,
        fg_color="#3a3a3c",
        hover_color=ACCENT_RED,
        corner_radius=12,
        state="disabled",
        command=on_reset,
    )
    reset_btn.pack(pady=8)

    # Status
    info_label = ctk.CTkLabel(
        card, text="SYSTEM READY", font=("Segoe UI", 12), text_color=TEXT_GREY
    )
    info_label.pack(pady=20)

    # Info icon
    info_icon = ctk.CTkLabel(
        app, text="ⓘ", font=("Segoe UI", 16), text_color=TEXT_GREY, cursor="hand2"
    )
    info_icon.place(relx=0.92, rely=0.97, anchor="center")
    info_icon.bind("<Button-1>", show_info)

    app.mainloop()


if __name__ == "__main__":
    main()
