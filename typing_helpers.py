from typing import TYPE_CHECKING, cast
import bpy

if TYPE_CHECKING:
    from .addon_data import VRCACTK_SceneData as SceneData


def get_scene_data(context: bpy.types.Context) -> 'SceneData':
    return cast('SceneData', getattr(context.scene, "VRCACTK"))

def get_armature_obj(context: bpy.types.Context) -> 'bpy.types.Object':
    scene_data = get_scene_data(context)
    return cast('bpy.types.Object', scene_data.selected_armature_obj)
