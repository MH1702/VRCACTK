import bpy

from .addon_data import VRCBTK_PropertyGroups_SceneData
from .util import registerme

@registerme
class VRCBTK_Operators_OpenNonHumanoidBoneMapModal(bpy.types.Operator):
    bl_idname = "vrcbtk.open_non_humanoid_bone_map_modal"
    bl_label = "Non-Humanoid Bones"

    @classmethod
    def register_me(cls):
        bpy.utils.register_class(cls)

    @classmethod
    def unregister_me(cls):
        bpy.utils.unregister_class(cls)

    def execute(self, context):
        bpy.ops.vrcbtk.non_humanoid_bone_map_modal('INVOKE_DEFAULT')

        return {'FINISHED'}

@registerme
class VRCBTK_Operators_NonHumanoidBoneMapModal(bpy.types.Operator):
    bl_idname = "vrcbtk.non_humanoid_bone_map_modal"
    bl_label = "Non-Humanoid Bones"

    @classmethod
    def register_me(cls):
        bpy.utils.register_class(cls)

    @classmethod
    def unregister_me(cls):
        bpy.utils.unregister_class(cls)

    armature_obj: bpy.types.Object | None = None

    non_humanoid_root_bones: list[bpy.types.Bone]

    def invoke(self, context, event=None):
        self.armature_obj = VRCBTK_PropertyGroups_SceneData.get_selected_armature_obj(context)

        self.non_humanoid_root_bones = []

        humanoid_armature_bone_names = [x.armature_bone_name for x in self.armature_obj.data.VRCBTK.bone_map]

        def recurse_bone_tree(bone: bpy.types.Bone):
            if bone.name not in humanoid_armature_bone_names:
                self.non_humanoid_root_bones.append(bone)
            else:
                for c in bone.children:
                    recurse_bone_tree(c)
        
        recurse_bone_tree(self.armature_obj.data.bones[0])
         
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        
        def recursive_draw_bone_tree(bone: bpy.types.Bone, layout: bpy.types.UILayout, depth = 0):
            layout.label(text=f"{'    ' * depth}{bone.name}")
            for c in bone.children:
                recursive_draw_bone_tree(c, layout, depth + 1)
        
        for b in self.non_humanoid_root_bones:
            recursive_draw_bone_tree(b, layout)
            layout.separator(type="LINE")

    def execute(self, context):
        return {'FINISHED'}

    def cancel(self, context):
        print("Modal dialog was canceled.")
