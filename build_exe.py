import PyInstaller.__main__
import shutil
import os
from pathlib import Path


def build_app():
    print("Building Mobile Diagnostic Tool Executable...")

    # Clean previous builds
    if os.path.exists("build"):
        shutil.rmtree("build")
    if os.path.exists("dist"):
        shutil.rmtree("dist")

    # verify customtkinter is installed
    try:
        import customtkinter

        ctk_path = os.path.dirname(customtkinter.__file__)
        print(f"Found CustomTkinter at: {ctk_path}")
    except ImportError:
        print("Error: customtkinter not installed. Run 'pip install customtkinter'")
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

    print("\nBuild Complete!")
    print("--------------------------------")
    print("Your app is in: dist/MobileDiagnosticTool/")
    print(
        "\nIMPORTANT: You must now copy your 'tools' folder into 'dist/MobileDiagnosticTool/tools'"
    )


if __name__ == "__main__":
    build_app()
