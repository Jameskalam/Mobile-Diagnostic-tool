import subprocess
from pathlib import Path
import sys
import re

# Determine base path for portability
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent

TOOLS_DIR = BASE_DIR / "tools"
SCRCPY_DIR = TOOLS_DIR / "android" / "scrcpy-win64-v3.3.4"
ADB_PATH = str(SCRCPY_DIR / "adb.exe")
AMA_PATH = TOOLS_DIR / "ios" / "AMA_iOS_Tool" / "AMA_iOS_Tool"
IDEVICE_ID_PATH = str(AMA_PATH / "idevice_id.exe")


class DeviceManager:
    @staticmethod
    def get_android_devices():
        """
        Returns a list of connected Android devices.
        Format: [{"id": "serial", "model": "Model Name", "status": "device/offline/unauthorized"}]
        """
        devices = []
        try:
            # Get list of devices
            result = subprocess.run(
                [ADB_PATH, "devices", "-l"],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            print(result.stdout)
            output = result.stdout.strip().splitlines()
            print(output)
            # Skip first line "List of devices attached"
            for line in output[1:]:
                print(line)
                if not line.strip():
                    continue

                parts = line.split()
                print(parts)
                serial = parts[0]
                print(serial)
                status = parts[1]
                print(status)

                # Extract model if available
                model = "Android Device"
                model_match = re.search(r"model:(\S+)", line)
                print(model_match)
                if model_match:
                    model = model_match.group(1).replace("_", " ")
                print(model)
                devices.append(
                    {
                        "id": serial,
                        "platform": "Android",
                        "model": model,
                        "status": status,
                        "label": f"{model} ({serial})",
                    }
                )
                print(devices)

        except Exception as e:
            print(f"Error getting Android devices: {e}")

        return devices

    @staticmethod
    def get_ios_devices():
        """
        Returns a list of connected iOS devices.
        Format: [{"id": "udid", "model": "iOS Device", "status": "connected"}]
        """
        devices = []
        try:
            if not Path(IDEVICE_ID_PATH).exists():
                return []

            result = subprocess.run(
                [IDEVICE_ID_PATH, "-l"],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            udids = result.stdout.strip().splitlines()

            for udid in udids:
                if not udid.strip():
                    continue

                # Ideally we would get the model name too, but ideviceinfo can be slow/flakey
                # For now, we'll just use "iOS Device"
                devices.append(
                    {
                        "id": udid.strip(),
                        "platform": "iOS",
                        "model": "iOS Device",
                        "status": "connected",
                        "label": f"iOS Device ({udid.strip()[:8]}...)",
                    }
                )

        except Exception as e:
            print(f"Error getting iOS devices: {e}")

        return devices

    @staticmethod
    def get_all_devices():
        return DeviceManager.get_android_devices() + DeviceManager.get_ios_devices()


if __name__ == "__main__":
    print("Searching for devices...")
    devices = DeviceManager.get_all_devices()
    if not devices:
        print("No devices found.")
    else:
        print(f"Found {len(devices)} device(s):")
        for dev in devices:
            print(f"- {dev['label']} (Status: {dev['status']})")
