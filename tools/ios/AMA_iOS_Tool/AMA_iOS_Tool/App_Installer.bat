@ECHO OFF

echo Drag and drop the iOS App installation file :
set /p app=
pause
echo Installing iOS App

ideviceinstaller.exe -i %app%