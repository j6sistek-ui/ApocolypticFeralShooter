"""Apply only the map/game mode settings required by the local prototype.

The native content must already be installed and authored. This script does not
download or publish assets. It preserves a dated configuration recovery copy.
"""
from datetime import datetime, timezone
from pathlib import Path
import re
import shutil

root = Path(__file__).resolve().parents[1]
config = root / "Config" / "DefaultEngine.ini"
backup = root / "Saved" / "HoverPrototype" / "ConfigRecovery"
backup.mkdir(parents=True, exist_ok=True)
stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
shutil.copy2(config, backup / f"DefaultEngine.{stamp}.ini")
text = config.read_text(encoding="utf-8-sig")
settings = {
    "EditorStartupMap": "/Game/JustBStudios/PostApo/Levels/PostApo.PostApo",
    "GameDefaultMap": "/Game/JustBStudios/PostApo/Levels/PostApo.PostApo",
    "GlobalDefaultGameMode": "/Script/HoverFlight.HoverGameMode",
}
for key, value in settings.items():
    pattern = rf"^{key}=.*$"
    if not re.search(pattern, text, re.MULTILINE):
        raise RuntimeError(f"Expected existing map setting missing: {key}")
    text = re.sub(pattern, f"{key}={value}", text, flags=re.MULTILINE)
config.write_text(text, encoding="utf-8")
print("Configured the PostApo level and HoverGameMode.")
