# -*- mode: python ; coding: utf-8 -*-


block_cipher = None


console_a = Analysis(
    ['src\\console.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['win32timezone'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
console_pyz = PYZ(console_a.pure, console_a.zipped_data, cipher=block_cipher)
console_exe = EXE(
    console_pyz,
    console_a.scripts,
    [],
    exclude_binaries=True,
    name='console',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)


service_a = Analysis(
    ['src\\start_service.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['win32timezone'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
service_pyz = PYZ(service_a.pure, service_a.zipped_data, cipher=block_cipher)
service_exe = EXE(
    service_pyz,
    service_a.scripts,
    [],
    exclude_binaries=True,
    name='start_service',
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
)

coll = COLLECT(
    console_exe,
    console_a.binaries,
    console_a.zipfiles,
    console_a.datas,
    service_exe,
    service_a.binaries,
    service_a.zipfiles,
    service_a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='bin',
)