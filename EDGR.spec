# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['code\\EDGR.py'],
    pathex=[],
    binaries=[('bin/vlc/libvlc.dll', 'bin/vlc'), ('bin/vlc/libvlccore.dll', 'bin/vlc'), ('bin/ffmpeg/ffmpeg.exe', 'bin/ffmpeg'), ('bin/ffmpeg/ffplay.exe', 'bin/ffmpeg'), ('bin/ffmpeg/ffprobe.exe', 'bin/ffmpeg')],
    datas=[('bin/vlc/plugins', 'bin/vlc/plugins'), ('assets', 'assets')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='EDGR',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets\\rabbit_icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='EDGR',
)
