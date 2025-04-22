import bpy

from .util import HUMANOID_BONE_DICT, HumanoidBone, registerme

@registerme
class VRCBTK_PropertyGroups_SceneData(bpy.types.PropertyGroup):
    @classmethod
    def register_me(cls) -> None:
        bpy.utils.register_class(cls)
        bpy.types.Scene.VRCBTK = bpy.props.PointerProperty(type=cls)
    
    @classmethod
    def unregister_me(cls) -> None:
        bpy.utils.unregister_class(cls)

    @classmethod
    def get_selected_armature_obj(cls, context: bpy.types.Context) -> bpy.types.Object | None: 
        selected_armature_obj_name = context.scene.VRCBTK.selected_armature
        selected_obj = bpy.data.objects.get(selected_armature_obj_name)
        if selected_obj is not None and selected_obj.type == 'ARMATURE':
            return selected_obj
        else: 
            return None

    selected_armature: bpy.props.EnumProperty(
        name="Selected Armature",
        description="Select the target armature for VRChat Blender Toolkit",
        items=lambda self, context: [
            (
                armature.name,
                armature.name,
                f"Select the '{armature.name}' armature",
                'ARMATURE_DATA',
                i
            )
            for i, armature in enumerate(
                [obj for obj in context.scene.objects if obj.type == 'ARMATURE']
            )
        ] if context and context.scene else []
    )

@registerme
class VRCBTK_Operators_SelectBone(bpy.types.Operator):
    bl_idname = "vrcbtk.select_bone"
    bl_label = "Select Bone"
    bl_options = {"UNDO"}

    @classmethod
    def register_me(cls):
        bpy.utils.register_class(cls)

    @classmethod
    def unregister_me(cls):
        bpy.utils.unregister_class(cls)

    armature_bone_name: bpy.props.StringProperty()

    def execute(self, context):
        if self.armature_bone_name == "None":
            return {"CANCELLED"}
        
        armature_obj = VRCBTK_PropertyGroups_SceneData.get_selected_armature_obj(context)
        
        if armature_obj:
            context.view_layer.objects.active = armature_obj
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.select_all(action='DESELECT')
            armature_obj.select_set(True)

            if self.armature_bone_name in armature_obj.data.bones:
                bone = armature_obj.data.bones[self.armature_bone_name]
                for bone_collection in armature_obj.data.collections:
                    if bone.name in bone_collection.bones and not bone_collection.is_visible:
                        bone_collection.is_visible = True
                        
            bpy.ops.object.mode_set(mode='EDIT')

            for edit_bone in armature_obj.data.edit_bones:
                state = edit_bone.name == self.armature_bone_name
                edit_bone.select = state
                edit_bone.select_head = state
                edit_bone.select_tail = state

        return {'FINISHED'}
    
@registerme
class VRCBTK_Operators_ResetBoneMappingSubtree(bpy.types.Operator):
    bl_idname = "vrcbtk.reset_bone_mapping_subtree"
    bl_label = "Reset bone mapping subtree"
    bl_options = {"UNDO"}

    @classmethod
    def register_me(cls):
        bpy.utils.register_class(cls)

    @classmethod
    def unregister_me(cls):
        bpy.utils.unregister_class(cls)

    humanoid_bone_name: bpy.props.StringProperty()

    def execute(self, context):
        armature_obj = VRCBTK_PropertyGroups_SceneData.get_selected_armature_obj(context)

        humanoid_bone = HUMANOID_BONE_DICT.get(self.humanoid_bone_name)
        bones_to_reset = [bone_name for (bone_name, properties) in HUMANOID_BONE_DICT.items() if (properties["path"] == humanoid_bone["path"] and properties["depth"] >= humanoid_bone["depth"]) or properties["path"].startswith(f"{humanoid_bone['path']}/")]

        for b in bones_to_reset:
            armature_obj.data.VRCBTK.get_mapping(b).armature_bone_name = "None"
       
        return {'FINISHED'}
    
@registerme
class VRCBTK_PropertyGroups_ArmatureData_HumanoidBoneMapping(bpy.types.PropertyGroup):
    @classmethod
    def register_me(cls) -> None:
        bpy.utils.register_class(cls)
    
    @classmethod
    def unregister_me(cls) -> None:
        bpy.utils.unregister_class(cls)

    humanoid_bone_name: bpy.props.StringProperty(
        name="Humanoid Bone",
        description="Name of the bone as per Unity's definition of 'Humanoid Bones'",
    )

    armature_bone_name: bpy.props.EnumProperty(
        name="Armature Bone",
        description="Name of the bone in the armature",
        items=lambda self, _: [
            ("None", "-", "No selection"), # Add an empty option as the default - note that blender throws a warning when the identifier itself is an empty string, hence why we use "None"
        ] + [
            (
                bone.name,
                bone.name,
                f"Bone: {bone.name}"
            )
            for bone in self.id_data.bones 
        ],
    )

    def draw(self, layout: bpy.types.UILayout):
        row = layout.row()

        humnaoid_bone = HUMANOID_BONE_DICT.get(self.humanoid_bone_name)

        row.label(text=f"{self.humanoid_bone_name}{'' if humnaoid_bone['required'] else '*'}")
        row.prop(self, "armature_bone_name", text="")

        has_selected = self.armature_bone_name != "None"

        col = row.column()
        col.enabled = has_selected

        select_bone_op = col.operator(VRCBTK_Operators_SelectBone.bl_idname, text="", icon="RESTRICT_SELECT_OFF")
        select_bone_op.armature_bone_name = self.armature_bone_name

        col = row.column()
        select_bone_op = col.operator(VRCBTK_Operators_ResetBoneMappingSubtree.bl_idname, text="", icon="X")
        select_bone_op.humanoid_bone_name = self.humanoid_bone_name

@registerme
class VRCBTK_PropertyGroups_ArmatureData_OptionalBoneMapping(bpy.types.PropertyGroup):
    @classmethod
    def register_me(cls) -> None:
        bpy.utils.register_class(cls)
    
    @classmethod
    def unregister_me(cls) -> None:
        bpy.utils.unregister_class(cls)

    humanoid_bone_name: bpy.props.StringProperty(
        name="Humanoid Bone",
        description="Name of the Humanoid Bone",
    )

    has: bpy.props.BoolProperty()

    def draw(self, layout: bpy.types.UILayout):
        row = layout.row()

        row.prop(self, "has", toggle=True, text=f"Has {self.humanoid_bone_name}?", expand=True)

@registerme
class VRCBTK_PropertyGroups_ArmatureData(bpy.types.PropertyGroup):
    @classmethod
    def register_me(cls) -> None:
        bpy.utils.register_class(cls)
        bpy.types.Armature.VRCBTK = bpy.props.PointerProperty(type=cls)
    
    @classmethod
    def unregister_me(cls) -> None:
        del bpy.types.Armature.VRCBTK
        bpy.utils.unregister_class(cls) 
    
    def reset_bone_mapping(self):
        """Add a new bone mapping to the collection."""
        self.bone_map.clear()
        for name in HumanoidBone.list():
            item = self.bone_map.add()
            item.humanoid_bone_name = name

    def ensure_mappings(self):
        if not self.optional_map:
            for humanoid_bone in [humanoid_bone for humanoid_bone, params in HUMANOID_BONE_DICT.items() if not params["required"]]:
                item = self.optional_map.add()
                item.humanoid_bone_name = humanoid_bone
                # TODO: Implement default value in params
                item.has = False

        if not self.bone_map:
            self.reset_bone_mapping()

    optional_map: bpy.props.CollectionProperty(type=VRCBTK_PropertyGroups_ArmatureData_OptionalBoneMapping)

    def get_optional_mapping(self, humanoid_bone_name: str):
        return next(
            (x for x in self.id_data.VRCBTK.optional_map if x.humanoid_bone_name == humanoid_bone_name),
            None
        )

    bone_map: bpy.props.CollectionProperty(type=VRCBTK_PropertyGroups_ArmatureData_HumanoidBoneMapping)

    def get_mapping(self, humanoid_bone_name: str):
        return next(
            (x for x in self.id_data.VRCBTK.bone_map if x.humanoid_bone_name == humanoid_bone_name),
            None
        )