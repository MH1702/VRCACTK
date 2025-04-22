import bpy

from .. import registerme

@registerme
class Operator_VRCBTK_MergeArmatures(bpy.types.Operator):
    bl_idname = "vrcbtk.merge_armatures"
    bl_label = "Merge Armatures"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def register_me(cls):
        bpy.utils.register_class(Operator_VRCBTK_MergeArmatures)

    @classmethod
    def unregister_me(cls):
        try:
            bpy.utils.unregister_class(Operator_VRCBTK_MergeArmatures)
        except RuntimeError:
            pass

    def execute(self, context):
        source_armature_name = context.scene.vrcbtk_selected_merge_armature
        target_armature_name = context.scene.vrcbtk_selected_armature

        target_armature_object = bpy.data.objects.get(target_armature_name)

        if not source_armature_name or source_armature_name == target_armature_object.name:
            self.report({'ERROR'}, "Invalid source armature selected")
            return {'CANCELLED'}

        source_armature_object = bpy.data.objects.get(source_armature_name)
        if not source_armature_object or source_armature_object.type != 'ARMATURE':
            self.report({'ERROR'}, "Source armature not found")
            return {'CANCELLED'}


        # Move all bones from source armature to target armature
        bpy.ops.object.mode_set(mode='OBJECT')
        target_armature_object.select_set(True)
        source_armature_object.select_set(True)
        bpy.context.view_layer.objects.active = source_armature_object
        # Apply transforms to the source armature
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

        bpy.ops.object.mode_set(mode='EDIT')
        bone_mapping = {}
        for bone in source_armature_object.data.edit_bones:
            new_bone = target_armature_object.data.edit_bones.new(bone.name + "_" + source_armature_name)
            new_bone.head = bone.head
            new_bone.tail = bone.tail
            new_bone.roll = bone.roll
            new_bone.use_connect = bone.use_connect
            bone_mapping[bone.name] = new_bone

        # Set parent relationships for the new bones
        for bone in source_armature_object.data.edit_bones:
            new_bone = bone_mapping[bone.name]
            if bone.parent:
                new_bone.parent = bone_mapping.get(bone.parent.name)

        bpy.ops.object.mode_set(mode='OBJECT')

        # Move everything from source armature to target armature
        for obj in bpy.data.objects:
            if obj.type == 'MESH' and obj.parent == source_armature_object:
                obj.parent = target_armature_object

                # Update armature modifier
                for modifier in obj.modifiers:
                    if modifier.type == 'ARMATURE' and modifier.object == source_armature_object:
                        modifier.object = target_armature_object

                # Transfer vertex groups
                for vgroup in obj.vertex_groups:
                    if vgroup.name in bone_mapping:
                        # Update vertex group name to match the new bone name in the target armature
                        vgroup.name = bone_mapping[vgroup.name].name

        # Remove the source armature
        bpy.data.objects.remove(source_armature_object, do_unlink=True)

        self.report({'INFO'}, "Moved all objects, bones, and vertex groups from source armature to target armature")
        return {'FINISHED'}
