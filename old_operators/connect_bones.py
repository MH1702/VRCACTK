import bpy

from .. import registerme

@registerme
class Operator_VRCBTK_ConnectBones(bpy.types.Operator):
    bl_idname = "vrcbtk.connect_bones"
    bl_label = "Connect Bones"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def register_me(cls):
        bpy.utils.register_class(cls)

    @classmethod
    def unregister_me(cls):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass

    def execute(self, context):
        obj = context.object

        if not obj or obj.type != 'ARMATURE':
            self.report({'ERROR'}, "Active object is not an armature")
            return {'CANCELLED'}

        if bpy.context.mode != 'EDIT_ARMATURE':
            self.report({'ERROR'}, "Must be in Edit Mode to connect bones")
            return {'CANCELLED'}

        tolerance = 0.001

        for bone in obj.data.edit_bones:
            for child in bone.children:
                if (bone.tail - child.head).length < tolerance:
                    child.use_connect = True

        self.report({'INFO'}, "Connected child bones to parent bones where applicable")
        return {'FINISHED'}
