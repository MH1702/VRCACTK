# The bl_info dictionary is necessary for Blender to identify the add-on.
bl_info = {
    "name": "VRCBTK",
    "author": "MH1702",
    "version": (1, 0, 0),
    "blender": (4, 1, 0), # Minimum Blender version required
    "location": "View3D > Sidebar > VRC Blender Toolkit", # Where the UI will appear (example)
    "description": "Toolkit for VRChat Avatar Creation",
    "warning": "", # Used for warnings (e.g., if the addon is experimental)
    "doc_url": "", # Link to documentation
    "category": "Development", # Add-on category in preferences
}

import bpy
import importlib

from . import addon_data, util, humanoid_bones, main_panel, non_humanoid_bones, parts

def reload_modules():
    """Reloads all modules in the addon package"""
    try:
        # NOTE: The order is important
        importlib.reload(util)
        importlib.reload(addon_data)

        importlib.reload(humanoid_bones)
        importlib.reload(non_humanoid_bones)
        importlib.reload(parts)
        importlib.reload(main_panel)
    except Exception as e:
        print(f"Error reloading VRCBTK modules: {e}")

# --- Function to Set Default Armature (runs AFTER load) ---
# Use @persistent to make sure the handler survives loading new files
@bpy.app.handlers.persistent
def set_default_armature_handler(dummy):
    """
    Checks and sets the default armature after a file load.
    Runs via load_post handler. Needs 'dummy' arg.
    """
    # Check if context and scene are usable now
    if not bpy.context or not bpy.context.scene:
        print("VRCBTK: Context or Scene not available in handler.")
        return

    current_selection = bpy.context.scene.VRCBTK.selected_armature

    # Only set default if the property is currently empty or points to an invalid object
    if not current_selection or current_selection not in bpy.data.objects:
        try:
            # Use the imported function to get items
            # Pass context directly now as it should be valid
            armatures_in_scene = [obj for obj in bpy.context.scene.objects if obj.type == 'ARMATURE']
            armature_names = [armature.name for armature in armatures_in_scene]
            if armature_names:
                # Assign to the property name
                bpy.context.scene.VRCBTK.selected_armature = armature_names[0]
        except Exception as e:
            print(f"VRCBTK: Error setting default armature via handler: {e}")

# --- Registration ---
def register():
    reload_modules()
    print(f"Registering: {bl_info['name']} v{bl_info['version']}")

    for registerable in util.registry.values():
        registerable.register_me()

    # --- Add the handler ---
    # Remove existing handler first to prevent duplicates during re-registration
    # (Important for development workflow)
    handlers = bpy.app.handlers.load_post
    for handler in list(handlers): # Iterate over a copy
        if handler.__name__ == set_default_armature_handler.__name__:
            handlers.remove(handler)
            print(f"VRCBTK: Removed existing '{handler.__name__}' handler.")

    # Add the new handler function to the load_post list
    handlers.append(set_default_armature_handler)
    print(f"VRCBTK: Added '{set_default_armature_handler.__name__}' handler.")

def unregister():
    print(f"Unregistering: {bl_info['name']}")

    # --- Remove the handler ---
    handlers = bpy.app.handlers.load_post
    for handler in list(handlers): # Iterate over a copy
        if handler.__name__ == set_default_armature_handler.__name__:
            try:
                handlers.remove(handler)
                print(f"VRCBTK: Removed '{handler.__name__}' handler.")
            except ValueError:
                # Handler might already be removed
                pass
            except Exception as e:
                print(f"VRCBTK: Error removing handler '{handler.__name__}': {e}")

    for registerable in util.registry.values():
        registerable.unregister_me()

