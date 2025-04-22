import bpy.types
import numpy as np

from .. import registerme

@registerme       
class Operator_VRCBTK_Normalize(bpy.types.Operator):
    bl_idname = "vrcbtk.normalize"
    bl_label = "Normalize"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def register_me(cls):
        bpy.utils.register_class(Operator_VRCBTK_Normalize)

    @classmethod
    def unregister_me(cls):
        try:
            bpy.utils.unregister_class(Operator_VRCBTK_Normalize)
        except RuntimeError:
            pass

    def execute(self, context):
        selected_armature_name = bpy.context.scene.VRCBTK.selected_armature
        armature = bpy.data.objects.get(selected_armature_name)

        if not armature or armature.type != 'ARMATURE':
            self.report({'ERROR'}, "Invalid armature selected")
            return {'CANCELLED'}
            
        def remove_unused_shape_keys(obj: bpy.types.Object):
            # Tolerance to small differences, change it if you want
            tolerance = 0.001

            assert bpy.context.mode == 'OBJECT', "Must be in object mode!"
            assert obj.type == 'MESH', "Object must be a mesh!"
            assert obj.data.shape_keys, "Object must have shape keys!"
            assert obj.data.shape_keys.use_relative, "Object must not use relative shape keys!"

            kbs = obj.data.shape_keys.key_blocks
            nverts = len(obj.data.vertices)
            to_delete = []

            # Cache locs for rel keys since many keys have the same rel key
            cache = {}

            locs = np.empty(3*nverts, dtype=np.float32)

            for kb in kbs:
                if kb == kb.relative_key: continue

                kb.data.foreach_get("co", locs)

                if kb.relative_key.name not in cache:
                    rel_locs = np.empty(3*nverts, dtype=np.float32)
                    kb.relative_key.data.foreach_get("co", rel_locs)
                    cache[kb.relative_key.name] = rel_locs
                rel_locs = cache[kb.relative_key.name]

                locs -= rel_locs
                if (np.abs(locs) < tolerance).all():
                    to_delete.append(kb.name)

            for kb_name in to_delete:
                obj.shape_key_remove(obj.data.shape_keys.key_blocks[kb_name])
                self.report({'INFO'}, f"Removed unused shape key '{kb_name}'")

        def remove_unused_materials(obj: bpy.types.Object):
            assert bpy.context.mode == 'OBJECT', "Must be in object mode!"
            assert obj.type == 'MESH', "Object must be a mesh!"
            assert obj.data, "Object must have mesh data!"
            
            used_materials = set()

            # Find all materials used by faces
            for poly in obj.data.polygons:
                used_materials.add(poly.material_index)

            # Remove unused materials
            unused_materials = [i for i in range(len(obj.data.materials)) if i not in used_materials]
            for index in sorted(unused_materials, reverse=True):
                material = obj.data.materials[index]
                obj.data.materials.pop(index=index)
                if material is None:
                    self.report({'INFO'}, f"Removed unused material")
                else:
                    self.report({'INFO'}, f"Removed unused material '{material.name}'")

        def remove_unused_vertex_groups(obj: bpy.types.Object):
            assert bpy.context.mode == 'OBJECT', "Must be in object mode!"
            assert obj.type == 'MESH', "Object must be a mesh!"
            assert obj.data, "Object must have mesh data!"

            used_groups = set()

            # Find all vertex groups used by vertices
            for vertex in obj.data.vertices:
                for group in vertex.groups:
                    used_groups.add(group.group)

            # Remove unused vertex groups
            unused_groups = [group for group in obj.vertex_groups if group.index not in used_groups]
            for group in unused_groups:
                vertex_group_name = group.name
                obj.vertex_groups.remove(group)
                self.report({'INFO'}, f"Removed unused vertex group '{vertex_group_name}'")

        def normalize_shape_keys(obj):
            if obj.data.shape_keys:
                remove_unused_shape_keys(obj)

                if len(obj.data.shape_keys.key_blocks) < 2:
                    obj.shape_key_clear()
                    self.report({'INFO'}, f"Cleared shape keys")
                else:
                    obj.data.shape_keys.name = obj.name
                    obj.data.shape_keys.key_blocks[0].name = "Basis"

        def normalize_recursively(obj: bpy.types.Object):
            if obj.type == 'MESH' and obj.data:
                # Rename Mesh Data
                obj.data.name = obj.name

                normalize_shape_keys(obj)

                remove_unused_materials(obj)
                
                remove_unused_vertex_groups(obj)
                        
            for child in obj.children:
                normalize_recursively(child)

        normalize_recursively(armature)
        
        self.report({'INFO'}, f"Successfully normalized '{armature.name}'")
        return {'FINISHED'}