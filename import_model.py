import bpy
from .util import registerme
from .typing_helpers import get_scene_data


@registerme
class VRCACTK_OT_ImportModel(bpy.types.Operator):
    bl_idname = "vrcactk.import_model"
    bl_label = "Import Model"

    @classmethod
    def register_me(cls):
        bpy.utils.register_class(cls)

    @classmethod
    def unregister_me(cls):
        bpy.utils.unregister_class(cls)

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    def execute(self, context):
        if context is None:
            return {'CANCELLED'}
        if context.scene is None:
            return {'CANCELLED'}
        
        # Import the FBX file with specific settings
        bpy.ops.import_scene.fbx(
            filepath=self.filepath,
            use_custom_normals=True,
            automatic_bone_orientation=True,
            use_prepost_rot=True,
            ignore_leaf_bones=True,
        )

        # NOTE: The newly imported object automatically gets selected by blender which we can use to find it
        imported_armature = None

        for obj in context.scene.objects:
            if obj.type == 'ARMATURE' and obj.select_get():
                imported_armature = obj
                break

        # Set the selected_armature property
        if imported_armature:
            scene_data = get_scene_data(context)
            scene_data.selected_armature_obj = imported_armature
            scene_data.armature_dropdown = imported_armature.name

        return {'FINISHED'}

    def invoke(self, context, event):
        if context is None:
            return {'CANCELLED'}
        
        # Open the file browser to select an FBX file
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
