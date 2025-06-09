@echo off
echo [🔧] Cleaning previous build files...
rmdir /s /q build
rmdir /s /q dist
del /q EDGR.spec

echo [🚀] Running PyInstaller...
python -m PyInstaller code\EDGR.py --noconfirm --clean --windowed ^
--icon=assets\rabbit_icon.ico ^
--add-binary "bin\vlc\libvlc.dll;bin/vlc" ^
--add-binary "bin\vlc\libvlccore.dll;bin/vlc" ^
--add-data "bin\vlc\plugins;bin/vlc/plugins" ^
--add-binary "bin\ffmpeg\ffmpeg.exe;bin/ffmpeg" ^
--add-binary "bin\ffmpeg\ffplay.exe;bin/ffmpeg" ^
--add-binary "bin\ffmpeg\ffprobe.exe;bin/ffmpeg" ^
--add-data "assets;assets"

echo [✅] Done. Check the dist\EDGR folder.
pause
