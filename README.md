# Mobile Diagnostic Pro

A standalone, powerful Desktop Application for capturing live logs, screen video, and device snapshots simultaneously from both Android and iOS devices.

## 🚀 For the Developer: How to Package & Distribute

If you want to give this tool to normal end-users (like QA testers or PMs) so they don't have to install Python, you can package it into a clean, standalone executable!

### 1. Install Build Dependencies
Open your command prompt in this folder and install PyInstaller:
```powershell
pip install -r requirements.txt
pip install pyinstaller
```

### 2. Build the Application
Run the automated build script:
```powershell
python build_exe.py
```
*This script will compile the code, bundle the beautiful UI theme, and automatically attach the iOS/Android `tools` library.*

### 3. Share it!
Navigate to `dist/MobileDiagnosticTool/`. This folder contains everything your users need! Simply ZIP this folder and send it to them.

---

## 🛠️ For the End-User: How to Use

When you receive the `MobileDiagnosticTool` folder, you **do not** need to install Python or use the command line!

### 1. Launching the App
Simply double-click **`MobileDiagnosticTool.exe`** inside the folder to launch the interface.

### 2. Operating the Tool
1. Plug your Android or iOS device into your PC via USB.
2. Click **↻ Refresh Devices** so it detects your phone.
3. Choose your Capture Mode (e.g., `Video + Log`, `Log Only`, etc.).
4. Hit **`Start Session`**!
5. Recreate your bugs/issues on the phone.
6. Hit **`Stop Session`**.
7. Click **`Export Data`** to cleanly save all the logs, screen recordings, and screenshots natively into a folder on your computer.

### Notes for Users:
- **Android:** Ensure "USB Debugging" is toggled ON in your phone's Developer Options.
- **iOS:** Ensure you select "Trust this Computer" when you plug the iPhone in. Due to Apple restrictions, video recording is disabled, but deep-system logs & snapshots work flawlessly!
- You can plug in multiple devices at once! Each device will get its own organized Tab.
