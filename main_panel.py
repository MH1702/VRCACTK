from typing import Any
import bpy

from .addon_data import VRCBTK_PropertyGroups_SceneData

from .non_humanoid_bones import VRCBTK_Operators_OpenNonHumanoidBoneMapModal

from .humanoid_bones import VRCBTK_Operators_OpenHumanoidBoneMapModal

from .parts import VRCBTK_Operators_OpenPartsModal

from .util import registerme

@registerme
class VRCBTK_PT_Panels_MainPanel(bpy.types.Panel):
    """Creates the main panel in the 3D View Sidebar"""
    bl_label = "VRC Blender Toolkit"
    bl_idname = "OBJECT_Panels_vrcbtk_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'VRCBTK' # Tab name in N-Panel

    @classmethod
    def register_me(cls):
        bpy.utils.register_class(cls)

    @classmethod
    def unregister_me(cls):
        bpy.utils.unregister_class(cls)

    def draw(self, context):
        """Defines how the panel's UI is drawn"""
        layout = self.layout

        layout.label(icon="WARNING_LARGE", text="This addon is still under development")

        # Check if any armatures exist
        armatures_in_scene = [obj for obj in context.scene.objects if obj.type == 'ARMATURE']

        if not armatures_in_scene:
            # If the list is empty, display an info message
            box = layout.box()
            box.label(text="No Armatures Found", icon='INFO')
        else:
            box = layout.box()
            box.label(text="Selected Armature:")
            box.prop(context.scene.VRCBTK, "selected_armature", text="")
            if context.mode != "OBJECT":
                box.operator(VRCBTK_OT_Operators_EnterObjectMode.bl_idname, icon="OBJECT_DATA")
            if context.mode != "EDIT_ARMATURE":
                box.operator(VRCBTK_OT_Operators_EnterEditMode.bl_idname, icon="EDITMODE_HLT")
            if context.mode != "POSE":
                box.operator(VRCBTK_OT_Operators_EnterPoseMode.bl_idname, icon="POSE_HLT")

            armature_obj_name = context.scene.VRCBTK.selected_armature

            armature_obj = context.scene.objects.get(armature_obj_name)
            if armature_obj:
                box = layout.box()

                row = box.row()
                row.alignment = "CENTER"
                row.label(text="Bones & Armature")
                             
                box.operator(
                    VRCBTK_Operators_OpenHumanoidBoneMapModal.bl_idname, 
                    icon='OUTLINER_OB_ARMATURE'
                )

                box.operator(
                    VRCBTK_Operators_OpenNonHumanoidBoneMapModal.bl_idname, 
                    icon='BONE_DATA'
                )

                box.operator(VRCBTK_Operators_SortBoneCollections.bl_idname)

                box = layout.box()
                row = box.row()
                row.alignment = "CENTER"
                row.label(text="Parts")

                box.operator(
                    VRCBTK_Operators_OpenPartsModal.bl_idname, 
                    icon='PACKAGE'
                )

                
@registerme
class VRCBTK_Operators_SortBoneCollections(bpy.types.Operator):
    bl_idname = "vrcbtk.sort_bone_collections"
    bl_label = "Sort Bone Collections"

    @classmethod
    def register_me(cls):
        bpy.utils.register_class(cls)

    @classmethod
    def unregister_me(cls):
        bpy.utils.unregister_class(cls)          

    def execute(self, context):
        armature_obj = VRCBTK_PropertyGroups_SceneData.get_selected_armature_obj(context)

        # Access the BoneCollections instance
        bone_collections = armature_obj.data.collections

        # Sort the collections by name
        sorted_collections = sorted(bone_collections, key=lambda x: x.name)

        for target_index, collection in enumerate(sorted_collections):
            current_index = bone_collections.find(collection.name)
            if current_index != target_index:
                bone_collections.move(current_index, target_index)

        return {'FINISHED'}

                    
@registerme
class VRCBTK_OT_Operators_EnterPoseMode(bpy.types.Operator):
    bl_idname = "vrcbtk.enter_pose_mode"
    bl_label = "Pose Mode"

    @classmethod
    def register_me(cls):
        bpy.utils.register_class(cls)

    @classmethod
    def unregister_me(cls):
        bpy.utils.unregister_class(cls)

    def execute(self, context):
        armature_obj = VRCBTK_PropertyGroups_SceneData.get_selected_armature_obj(context)
        
        context.view_layer.objects.active = armature_obj
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        armature_obj.select_set(True)

        bpy.ops.object.mode_set(mode='POSE')

        return {'FINISHED'}
    
@registerme
class VRCBTK_OT_Operators_EnterObjectMode(bpy.types.Operator):
    bl_idname = "vrcbtk.enter_object_mode"
    bl_label = "Object Mode"

    @classmethod
    def register_me(cls):
        bpy.utils.register_class(cls)

    @classmethod
    def unregister_me(cls):
        bpy.utils.unregister_class(cls)

    def execute(self, context):
        armature_obj = VRCBTK_PropertyGroups_SceneData.get_selected_armature_obj(context)
        
        context.view_layer.objects.active = armature_obj
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        armature_obj.select_set(True)

        return {'FINISHED'}
    
@registerme
class VRCBTK_OT_Operators_EnterEditMode(bpy.types.Operator):
    bl_idname = "vrcbtk.enter_edit_mode"
    bl_label = "Edit Mode"

    @classmethod
    def register_me(cls):
        bpy.utils.register_class(cls)

    @classmethod
    def unregister_me(cls):
        bpy.utils.unregister_class(cls)

    def execute(self, context):
        armature_obj = VRCBTK_PropertyGroups_SceneData.get_selected_armature_obj(context)
        
        context.view_layer.objects.active = armature_obj
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        armature_obj.select_set(True)

        bpy.ops.object.mode_set(mode='EDIT')

        return {'FINISHED'}