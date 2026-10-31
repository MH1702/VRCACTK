"""Run with Blender --background --factory-startup --python-exit-code 1."""
import contextlib
import importlib
import io
from pathlib import Path
import sys
import tempfile
import zipfile

import addon_utils
import bpy

archive = Path(sys.argv[sys.argv.index("--") + 1]).resolve()
with tempfile.TemporaryDirectory(prefix="vrcactk-smoke-") as directory:
    repo = bpy.context.preferences.extensions.repos.new(
        name="VRCACTK Test", module="vrcactk_test", custom_directory=directory,
    )
    target = Path(directory) / "vrcactk"
    with zipfile.ZipFile(archive) as package:
        package.extractall(target)
    module_name = "bl_ext.vrcactk_test.vrcactk"
    output = io.StringIO()
    try:
        with contextlib.redirect_stdout(output):
            for _ in range(2):
                addon_utils.enable(module_name, default_set=True)
                assert addon_utils.check(module_name)[1], "Extension did not enable"
                module = importlib.import_module(module_name)
                classes = [cls for cls in module.util.registry.values()
                           if hasattr(cls, "is_registered")]
                assert classes, "No classes registered"
                missing = [cls.__name__ for cls in classes if not cls.is_registered]
                assert not missing, f"Unregistered classes: {missing}"
                addon_utils.disable(module_name, default_set=True)
                assert not addon_utils.check(module_name)[1], "Extension did not disable"
                assert all(not cls.is_registered for cls in classes), "Classes leaked"
        log = output.getvalue()
        assert "failed" not in log.lower() and "error" not in log.lower(), log
    finally:
        print(output.getvalue())
        bpy.context.preferences.extensions.repos.remove(repo)
print("Extension package enable/disable/re-enable smoke test passed")
