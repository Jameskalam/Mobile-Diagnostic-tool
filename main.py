import threading
from pathlib import Path
from tkinter import filedialog, messagebox
import customtkinter as ctk

from android_handler import AndroidSession
from ios_handler import IOSSession

AMAZON_ORANGE = "#FF9900"
CARD_BG = "#1e1e1e"

def main():
    state = {"session": None}

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")

    app = ctk.CTk()
    app.title("Mobile Diagnostic Tool")
    app.geometry("480x700")
    app.resizable(False, False)

    # ---------------- INFO ----------------
    def show_info(event):
        messagebox.showinfo(
            "AMQE Tool",
            "Mobile Diagnostic Workstation\nVersion 2.1"
        )

    # ---------------- START ----------------
    def on_start():
        start_btn.configure(state="disabled")

        platform = platform_dropdown.get()
        capture_mode = capture_dropdown.get()

        info_label.configure(
            text=f"INITIALIZING {platform}...",
            text_color=AMAZON_ORANGE
        )

        def run():
            # ---------- iOS restrictions ----------
            if platform == "iOS":
                # iOS cannot start video only
                if capture_mode == "Video Only":
                    app.after(0, lambda: messagebox.showinfo(
                        "Info",
                        "iOS cannot start video automatically.\nPlease select 'Log Only' or 'Both'."
                    ))
                    app.after(0, lambda: start_btn.configure(state="normal"))
                    return

                state["session"] = IOSSession()

                # Check iOS connection
                if not state["session"].is_connected():
                    app.after(0, lambda: [
                        messagebox.showerror("Error", "iOS device not found!"),
                        start_btn.configure(state="normal"),
                        stop_btn.configure(state="disabled"),
                        save_btn.configure(state="disabled"),
                        info_label.configure(text="SYSTEM READY", text_color="#95a5a6")
                    ])
                    return

                # Start log capture
                state["session"].start()
                app.after(0, lambda: [
                    stop_btn.configure(state="normal"),
                    info_label.configure(
                        text="● LOG RECORDING iOS",
                        text_color="#e74c3c"
                    )
                ])
                return

            # ---------- Android ----------
            state["session"] = AndroidSession(capture_mode)
            if not state["session"].is_connected():
                app.after(0, lambda: [
                    messagebox.showerror("Error", "Android device not found!"),
                    start_btn.configure(state="normal"),
                    stop_btn.configure(state="disabled"),
                    save_btn.configure(state="disabled"),
                    info_label.configure(text="SYSTEM READY", text_color="#95a5a6")
                ])
                return

            state["session"].start()
            app.after(0, lambda: [
                stop_btn.configure(state="normal"),
                info_label.configure(
                    text=f"● RECORDING Android ({capture_mode})",
                    text_color="#e74c3c"
                )
            ])

        threading.Thread(target=run, daemon=True).start()

    # ---------------- STOP ----------------
    def on_stop():
        if not state["session"]:
            return

        info_label.configure(
            text="FINALIZING SESSION...",
            text_color=AMAZON_ORANGE
        )

        def run():
            state["session"].stop()
            app.after(0, lambda: [
                start_btn.configure(state="normal"),
                stop_btn.configure(state="disabled"),
                save_btn.configure(state="normal"),
                info_label.configure(
                    text="STOPPED – READY TO EXPORT",
                    text_color="#2ecc71"
                )
            ])

        threading.Thread(target=run, daemon=True).start()

    # ---------------- SAVE ----------------
    def on_save():
        folder = filedialog.askdirectory()
        if folder:
            success, msg = state["session"].save(Path(folder))
            messagebox.showinfo("Export Result", msg)

    # ---------------- HEADER ----------------
    ctk.CTkLabel(
        app, text="amazon", font=("Arial", 48, "bold")
    ).pack(pady=(30, 0))

    ctk.CTkLabel(
        app,
        text="DIAGNOSTIC WORKSTATION",
        font=("Verdana", 14, "bold"),
        text_color="#3498db"
    ).pack(pady=(0, 30))

    # ---------------- CARD ----------------
    card = ctk.CTkFrame(app, fg_color=CARD_BG, corner_radius=18)
    card.pack(padx=25, pady=10, fill="both", expand=True)

    # Platform selector
    ctk.CTkLabel(card, text="Platform", font=("Arial", 13, "bold")).pack(pady=(20, 5))
    platform_dropdown = ctk.CTkOptionMenu(
        card,
        values=["Android", "iOS"],
        width=260,
        fg_color="#2a2a2a",
        button_color=AMAZON_ORANGE
    )
    platform_dropdown.set("Android")
    platform_dropdown.pack(pady=(0, 15))

    # Capture selector
    ctk.CTkLabel(card, text="Capture Mode", font=("Arial", 13, "bold")).pack(pady=(10, 5))
    capture_dropdown = ctk.CTkOptionMenu(
        card,
        values=["Video + Log", "Video Only", "Log Only"],
        width=260,
        fg_color="#2a2a2a",
        button_color="#3498db"
    )
    capture_dropdown.set("Video + Log")
    capture_dropdown.pack(pady=(0, 25))

    # Disable "Video Only" option when iOS is selected
    def update_capture_options(platform):
        if platform == "iOS":
            capture_dropdown.configure(values=["Log Only", "Video + Log"])
            capture_dropdown.set("Log Only")
        else:
            capture_dropdown.configure(values=["Video + Log", "Video Only", "Log Only"])
            capture_dropdown.set("Video + Log")

    platform_dropdown.configure(command=update_capture_options)

    # Buttons
    start_btn = ctk.CTkButton(
        card,
        text="START TEST",
        height=50,
        width=260,
        font=("Arial", 14, "bold"),
        fg_color="#2ecc71",
        command=on_start
    )
    start_btn.pack(pady=8)

    stop_btn = ctk.CTkButton(
        card,
        text="STOP TEST",
        height=50,
        width=260,
        font=("Arial", 14, "bold"),
        fg_color="#e74c3c",
        state="disabled",
        command=on_stop
    )
    stop_btn.pack(pady=8)

    save_btn = ctk.CTkButton(
        card,
        text="EXPORT SESSION DATA",
        height=50,
        width=260,
        font=("Arial", 14, "bold"),
        state="disabled",
        command=on_save
    )
    save_btn.pack(pady=(25, 10))

    # Status
    info_label = ctk.CTkLabel(
        app,
        text="SYSTEM READY",
        font=("Consolas", 13),
        text_color="#95a5a6"
    )
    info_label.pack(pady=15)

    # Info icon
    info_icon = ctk.CTkLabel(
        app,
        text="ⓘ",
        font=("Arial", 20, "bold"),
        text_color="#555555",
        cursor="hand2"
    )
    info_icon.place(relx=0.94, rely=0.96, anchor="center")
    info_icon.bind("<Button-1>", show_info)

    app.mainloop()


if __name__ == "__main__":
    main()
