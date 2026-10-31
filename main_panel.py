import bpy

from .util_operations import VRCACTK_OT_ListShapeKeysAffectingSelectionOperator, VRCACTK_OT_RemoveUnusedVertexGroupsOperator, VRCACTK_OT_RemoveUnusedAttributesOperator, VRCACTK_OT_RemoveUnusedMaterialSlotsOperator, VRCACTK_OT_RemoveUnusedShapeKeysOperator, VRCACTK_OT_SelectVerticesAffectedByShapeKeyOperator, VRCACTK_OT_ReportIssuesOperator

from .import_model import VRCACTK_OT_ImportModel
from .export_avatar import VRCACTK_OT_ExportAvatar

from .util import registerme
from .typing_helpers import get_scene_data

@registerme
class VRCACTK_PT_MainPanel(bpy.types.Panel):
    bl_label = "VRC Avatar Creation Toolkit"
    bl_idname = "OBJECT_PT_vrcactk_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'VRCACTK' # Tab name in N-Panel

    @classmethod
    def register_me(cls):
        bpy.utils.register_class(cls)

    @classmethod
    def unregister_me(cls):
        bpy.utils.unregister_class(cls)

    def draw(self, context):
        if context is None:
            return
        if context.scene is None:
            return

        self.layout.label(icon="ERROR", text="This addon is still under development")

        scene_data = get_scene_data(context)

        armatures_in_scene = [obj for obj in context.scene.objects if obj.type == 'ARMATURE']

        if not armatures_in_scene:
            box = self.layout.box()
            box.operator(VRCACTK_OT_ImportModel.bl_idname, icon="IMPORT")
        else:
            box = self.layout.box()

            box.label(text="Avatar:")

            scene_data = get_scene_data(context)
            box.prop(scene_data, "armature_dropdown", text="")

            # box.operator(VRCACTK_OT_RemoveUnusedVertexGroupsOperator.bl_idname, icon="GROUP_VERTEX")
            # box.operator(VRCACTK_OT_RemoveUnusedAttributesOperator.bl_idname, icon="MOD_DATA_TRANSFER")
            # box.operator(VRCACTK_OT_RemoveUnusedMaterialSlotsOperator.bl_idname, icon="MATERIAL_DATA")
            # box.operator(VRCACTK_OT_RemoveUnusedShapeKeysOperator.bl_idname, icon="SHAPEKEY_DATA")
            box.operator(VRCACTK_OT_ReportIssuesOperator.bl_idname, icon="INFO")

            export_box = self.layout.box()
            export_box.label(text="Export:")
            export_box.operator(VRCACTK_OT_ExportAvatar.bl_idname, icon="EXPORT")
