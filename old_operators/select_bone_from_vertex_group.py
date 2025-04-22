import bpy.types

from .. import registerme

@registerme
class Operator_VRCBTK_SelectBoneFromVertexGroup(bpy.types.Operator):
    bl_idname = "vrcbtk.select_bone_from_vertex_group"
    bl_label = "Select Bone from Vertex Group"
    bl_description = "Select the bone in the armature corresponding to the vertex group"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def register_me(cls):
        bpy.utils.register_class(Operator_VRCBTK_SelectBoneFromVertexGroup)
        bpy.types.UI_MT_list_item_context_menu.append(add_select_bone_option)

    @classmethod
    def unregister_me(cls):
        bpy.types.UI_MT_list_item_context_menu.remove(add_select_bone_option)
        try:
            bpy.utils.unregister_class(Operator_VRCBTK_SelectBoneFromVertexGroup)
        except RuntimeError:
            pass

    def execute(self, context):
        obj = context.object

        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "Active object is not a mesh")
            return {'CANCELLED'}

        armature_obj: bpy.types.Object = obj.find_armature()
        if not armature_obj:
            self.report({'ERROR'}, "No armature found for the active object")
            return {'CANCELLED'}


        bpy.ops.object.mode_set(mode='OBJECT')
        context.view_layer.objects.active = armature_obj
        # Select the bone in the armature
        bpy.ops.object.mode_set(mode='EDIT')
        for bone in armature_obj.data.edit_bones:
            bone.select = False
            bone.select_head = False
            bone.select_tail = False

        armature_bone_name = context.button_pointer.active.name
        bone = armature_obj.data.edit_bones.get(armature_bone_name)
        if not bone:
            self.report({'ERROR'}, f"No bone found with the name '{armature_bone_name}'")
            return {'CANCELLED'}

        # Unhide the bone if it is in a hidden bone collection
        for bone_collection in armature_obj.data.collections:
            if bone.name in bone_collection.bones and not bone_collection.is_visible:
                bone_collection.is_visible = True

        bone.select = True
        bone.select_head = True
        bone.select_tail = True
        
        armature_obj.data.edit_bones.active = bone

        self.report({'INFO'}, f"Selected bone '{armature_bone_name}'")
        return {'FINISHED'}

# Extend the context menu for vertex groups
def add_select_bone_option(self, context):
    if isinstance(context.button_pointer, bpy.types.VertexGroups):
        self.layout.operator(Operator_VRCBTK_SelectBoneFromVertexGroup.bl_idname)