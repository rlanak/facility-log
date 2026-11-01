"""Creates a "Facility Log" shortcut on the Windows desktop that starts the app
in tray mode (no console window): .venv\\Scripts\\pythonw.exe run.py --tray.

    .venv/Scripts/python.exe scripts/create_shortcut.py

Re-run it if the project folder moves.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYTHONW = ROOT / ".venv" / "Scripts" / "pythonw.exe"
ICON = ROOT / "data" / "facility_log.ico"


def main() -> None:
    if not PYTHONW.is_file():
        raise SystemExit(f"{PYTHONW} not found — create the venv first (see CLAUDE.md, 'Como rodar').")

    sys.path.insert(0, str(ROOT))
    from run import _tray_image  # same icon as the tray

    ICON.parent.mkdir(exist_ok=True)
    _tray_image().save(ICON, sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])

    # WScript.Shell is the stock way to write a .lnk without extra packages.
    # UTF-8 output: the desktop folder name can have accents (localized
    # Windows, OneDrive "Área de Trabalho").
    script = f"""
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$desktop = [Environment]::GetFolderPath('Desktop')
$lnk = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $desktop 'Facility Log.lnk'))
$lnk.TargetPath = '{PYTHONW}'
$lnk.Arguments = '"{ROOT / "run.py"}" --tray'
$lnk.WorkingDirectory = '{ROOT}'
$lnk.IconLocation = '{ICON}'
$lnk.Description = 'Facility Log (Foxhole)'
$lnk.Save()
Write-Output (Join-Path $desktop 'Facility Log.lnk')
"""
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script], capture_output=True, encoding="utf-8", check=True
    )
    print("Atalho criado:", result.stdout.strip())


if __name__ == "__main__":
    main()
