from typing import Any
import bpy

from .addon_data import VRCBTK_PropertyGroups_SceneData
from .util import registerme

@registerme
class VRCBTK_Operators_OpenPartsModal(bpy.types.Operator):
    bl_idname = "vrcbtk.open_parts_modal"
    bl_label = "Parts"

    @classmethod
    def register_me(cls):
        bpy.utils.register_class(cls)

    @classmethod
    def unregister_me(cls):
        bpy.utils.unregister_class(cls)

    def execute(self, context):
        bpy.ops.vrcbtk.parts_modal('INVOKE_DEFAULT')

        return {'FINISHED'}


@registerme
class VRCBTK_PropertyGroup_PartFoldout(bpy.types.PropertyGroup):
    expanded: bpy.props.BoolProperty()
    path: bpy.props.StringProperty()
    depth: bpy.props.IntProperty()

    @classmethod
    def register_me(cls):
        bpy.utils.register_class(cls)

    @classmethod
    def unregister_me(cls):
        bpy.utils.unregister_class(cls)

@registerme
class VRCBTK_Operators_PartsModal(bpy.types.Operator):
    bl_idname = "vrcbtk.parts_modal"
    bl_label = "Parts"

    @classmethod
    def register_me(cls):
        bpy.utils.register_class(cls)

    @classmethod
    def unregister_me(cls):
        bpy.utils.unregister_class(cls)

    armature_obj: bpy.types.Object | None = None

    parts: bpy.props.CollectionProperty(type=VRCBTK_PropertyGroup_PartFoldout)

    def invoke(self, context, event=None):
        self.armature_obj = VRCBTK_PropertyGroups_SceneData.get_selected_armature_obj(context)

        for c in self.armature_obj.children:
            path_components = c.name.split("|")

            path = ""
            depth = 0

            for i, path_component in enumerate(path_components):
                if i > 0:
                    path += "|"
                path += path_component
                if not next(iter([p for p in self.parts if p.path == path]), None):
                    item = self.parts.add()
                    item.path = path
                    item.depth = depth
                depth += 1
         
        return context.window_manager.invoke_props_dialog(self)

    def draw_part(self, context: bpy.types.Context, layout: bpy.types.UILayout, part):
        box = layout.box()
        row = box.row()
        row.prop(part, "expanded", icon="DOWNARROW_HLT" if part.expanded else "RIGHTARROW", text=part.path.replace("|", " / "))

        if part.expanded:
            has_object = part.path in [o.name for o in self.armature_obj.children]
            box.label(text="Object", icon="CHECKBOX_HLT" if has_object else "CHECKBOX_DEHLT")
            box.label(text="Bone Collection", icon="CHECKBOX_HLT" if part.path in self.armature_obj.data.collections else "CHECKBOX_DEHLT")

            isolate_op = box.operator(VRCBTK_Operators_IsolatePart.bl_idname)
            isolate_op.path = part.path

            child_parts = [c for c in self.parts if c.path.startswith(part.path) and c.depth == part.depth + 1]
            if child_parts:
                for c in child_parts:
                    self.draw_part(context, box, c)
    def draw(self, context):
        layout = self.layout

        root_parts = [part for part in self.parts if "|" not in part.path]
        for part in root_parts:
            self.draw_part(context, layout, part)

    def execute(self, context):
        return {'FINISHED'}

    def cancel(self, context):
        print("Modal dialog was canceled.")

@registerme
class VRCBTK_Operators_IsolatePart(bpy.types.Operator):
    bl_idname = "vrcbtk.isolate_part"
    bl_label = "Isolate Part"
    bl_options = {"UNDO"}

    @classmethod
    def register_me(cls):
        bpy.utils.register_class(cls)

    @classmethod
    def unregister_me(cls):
        bpy.utils.unregister_class(cls)

    path: bpy.props.StringProperty()


    def execute(self, context):
        armature_obj: bpy.types.Object = VRCBTK_PropertyGroups_SceneData.get_selected_armature_obj(context)

        armature_obj.hide_set(False)
        context.view_layer.objects.active = armature_obj
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        bpy.ops.object.hide_view_set(unselected=True)
        armature_obj.hide_set(False)

        for bone_collection in armature_obj.data.collections_all:
            bone_collection.is_solo = False
            bone_collection.is_visible = bone_collection.name == self.path or bone_collection.name.startswith(self.path + "|")
        
        objects = [o for o in armature_obj.children if o.name == self.path or o.name.startswith(self.path + "|")]
        for o in objects:
            o.hide_set(False)
            o.select_set(True)
        
        return {'FINISHED'}