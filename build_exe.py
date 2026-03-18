import PyInstaller.__main__
import shutil
import os
from pathlib import Path


def build_app():
    # Clean previous builds
    if os.path.exists("build"):
        shutil.rmtree("build")
    if os.path.exists("dist"):
        shutil.rmtree("dist")

    # verify customtkinter is installed
    try:
        import customtkinter

        ctk_path = os.path.dirname(customtkinter.__file__)
    except ImportError:
        return

    PyInstaller.__main__.run(
        [
            "main.py",
            "--name=MobileDiagnosticTool",
            "--noconfirm",
            "--windowed",  # No console window
            "--icon=NONE",  # Standard icon for now
            f"--add-data={ctk_path};customtkinter",  # Embed theme files
            "--clean",
        ]
    )

    # Automate copying the 'tools' folder for a clean finish!
    source_tools = Path("tools")
    dest_tools = Path("dist/MobileDiagnosticTool/tools")
    if source_tools.exists():
        shutil.copytree(source_tools, dest_tools, dirs_exist_ok=True)


if __name__ == "__main__":
    build_app()
