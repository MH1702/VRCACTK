"""Build a clean extension using Blender's official packaging tools."""
import argparse
import ast
from pathlib import Path
import shutil
import subprocess
import tempfile
import tomllib

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_FILES = (
    "__init__.py", "addon_data.py", "export_avatar.py", "import_model.py",
    "main_panel.py", "typing_helpers.py", "util.py", "util_operations.py",
    "blender_manifest.toml", "LICENSE", "README.md",
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blender", default="blender")
    parser.add_argument("--tag", help="Require this tag to match the manifest version")
    args = parser.parse_args()
    manifest = tomllib.loads((ROOT / "blender_manifest.toml").read_text())
    if args.tag and args.tag != "v" + manifest["version"]:
        parser.error("Release tag must equal v" + manifest["version"])
    output = ROOT / "dist"
    output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="vrcactk-build-") as directory:
        stage = Path(directory)
        for name in PACKAGE_FILES:
            source = ROOT / name
            if source.suffix == ".py":
                ast.parse(source.read_text(encoding="utf-8"), filename=name)
            shutil.copy2(source, stage / name)
        subprocess.run([
            args.blender, "--background", "--factory-startup", "--command",
            "extension", "build", "--source-dir", str(stage),
            "--output-dir", str(output),
        ], check=True)
    archive = output / f"{manifest['id']}-{manifest['version']}.zip"
    subprocess.run([
        args.blender, "--background", "--factory-startup", "--command",
        "extension", "validate", str(archive),
    ], check=True)
    print(archive)


if __name__ == "__main__":
    main()
