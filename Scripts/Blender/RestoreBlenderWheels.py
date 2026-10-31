"""Restore Blender 5.2 extension wheels (PIL, cv2, trimesh...) that a factory-settings reset removes.
Run: blender.exe -b --python Scripts/Blender/RestoreBlenderWheels.py  (user prefs, never --factory-startup)."""
import addon_utils, os
addon_utils.extensions_refresh(ensure_wheels=True)
p = os.path.expandvars(r'%APPDATA%\Blender Foundation\Blender\5.2\extensions\.local\lib\python3.13\site-packages')
print('WHEELS', len(os.listdir(p)) if os.path.isdir(p) else 'MISSING')
