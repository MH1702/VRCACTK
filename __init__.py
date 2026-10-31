# Extension metadata lives in blender_manifest.toml.

import bpy
import importlib

from . import (
    util,
    addon_data,
    import_model,
    export_avatar,
    util_operations,
    main_panel,
)

def reload_modules():
    """Reloads all modules in the addon package"""
    try:
        # NOTE: The order is important
        importlib.reload(util)

        # Reload all modules that register classes via @registerme.
        importlib.reload(addon_data)
        importlib.reload(import_model)
        importlib.reload(export_avatar)
        importlib.reload(util_operations)
        importlib.reload(main_panel)
    except Exception as e:
        print(f"Error reloading VRCACTK modules: {e}")


# --- Registration ---
def _maybe_unregister_by_name(class_name: str) -> None:
    existing = getattr(bpy.types, class_name, None)
    if existing is None:
        return
    try:
        bpy.utils.unregister_class(existing)
    except Exception as e:
        print(f"VRCACTK pre-unregister failed for {class_name}: {e}")


def register():
    if bpy.app.version < (4, 2, 0):
        raise RuntimeError("VRCACTK requires Blender 4.2 or newer")

    reload_modules()

    print("Registering: VRCACTK")

    for registerable in util.registry.values():
        _maybe_unregister_by_name(registerable.__name__)
        try:
            registerable.register_me()
        except Exception as e:
            message = str(e)
            if "already registered" in message:
                try:
                    registerable.unregister_me()
                    registerable.register_me()
                except Exception as retry_error:
                    print(
                        "VRCACTK register retry failed for "
                        f"{registerable.__name__}: {retry_error}"
                    )
            else:
                print(f"VRCACTK register failed for {registerable.__name__}: {e}")

def unregister():
    print("Unregistering: VRCACTK")

    for registerable in reversed(list(util.registry.values())):
        try:
            registerable.unregister_me()
        except Exception as e:
            print(f"VRCACTK unregister failed for {registerable.__name__}: {e}")

