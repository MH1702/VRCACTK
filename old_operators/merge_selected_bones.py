import bpy

from .. import registerme

@registerme
class Operator_VRCBTK_MergeSelectedBones(bpy.types.Operator):
    bl_idname = "vrcbtk.merge_selected_bones"
    bl_label = "Merge Selected Bones"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def register_me(cls):
        bpy.utils.register_class(Operator_VRCBTK_MergeSelectedBones)

    @classmethod
    def unregister_me(cls):
        try:
            bpy.utils.unregister_class(Operator_VRCBTK_MergeSelectedBones)
        except RuntimeError:
            pass

    def execute(self, context):
        obj = context.object

        if not obj or obj.type != 'ARMATURE':
            self.report({'ERROR'}, "Active object is not an armature")
            return {'CANCELLED'}

        if bpy.context.mode != 'EDIT_ARMATURE':
            self.report({'ERROR'}, "Must be in Edit Mode to merge bones")
            return {'CANCELLED'}

        armature = obj
        active_bone = armature.data.edit_bones.active
        selected_bones = [bone for bone in armature.data.edit_bones if bone.select and bone != active_bone]

        if not active_bone or len(selected_bones) < 1:
            self.report({'ERROR'}, "No active bone or not enough selected bones")
            return {'CANCELLED'}

        # Transfer vertex groups
        for mesh_obj in bpy.data.objects:
            if mesh_obj.type == 'MESH' and mesh_obj.parent == armature:
                for bone in selected_bones:
                    vg_from = mesh_obj.vertex_groups.get(bone.name)
                    vg_to = mesh_obj.vertex_groups.get(active_bone.name)

                    if vg_from:
                        if not vg_to:
                            vg_to = mesh_obj.vertex_groups.new(name=active_bone.name)

                        for vert in mesh_obj.data.vertices:
                            for group in vert.groups:
                                if group.group == vg_from.index:
                                    vg_to.add([vert.index], group.weight, 'ADD')

                        # Remove the old vertex group
                        mesh_obj.vertex_groups.remove(vg_from)

        # Delete the selected bones
        for bone in selected_bones:
            armature.data.edit_bones.remove(bone)

        self.report({'INFO'}, "Merged selected bones into active bone")
        return {'FINISHED'}
