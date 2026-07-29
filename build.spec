# Build with: pyinstaller build.spec
# (from inside the print-agent/ directory, with requirements.txt + pyinstaller installed)
# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['agent.py'],
    pathex=[],
    binaries=[],
    datas=[('config.example.json', '.')],
    hiddenimports=['usb.backend.libusb1'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='shazada-print-agent',
    console=True,
    onefile=True,
)
