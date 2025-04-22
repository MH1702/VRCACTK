import bpy
import mathutils

from .addon_data import VRCBTK_PropertyGroups_SceneData
from .util import HUMANOID_BONE_DICT, HUMANOID_BONES_BY_CATEGORY, HumanoidBone, get_armature_by_object_name, registerme

@registerme
class VRCBTK_Operators_OpenHumanoidBoneMapModal(bpy.types.Operator):
    bl_idname = "vrcbtk.open_humanoid_bone_map_modal"
    bl_label = "Humanoid Bones"

    @classmethod
    def register_me(cls):
        bpy.utils.register_class(cls)

    @classmethod
    def unregister_me(cls):
        bpy.utils.unregister_class(cls)

    def execute(self, context):
        bpy.ops.vrcbtk.humanoid_bone_map_modal('INVOKE_DEFAULT')

        return {'FINISHED'}

@registerme
class VRCBTK_Operators_HumanoidBoneMapModal(bpy.types.Operator):
    bl_idname = "vrcbtk.humanoid_bone_map_modal"
    bl_label = "Humanoid Bones"

    @classmethod
    def register_me(cls):
        bpy.utils.register_class(cls)

    @classmethod
    def unregister_me(cls):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass

    armature_obj: bpy.types.Object | None = None

    def invoke(self, context, event=None):
        self.armature_obj = VRCBTK_PropertyGroups_SceneData.get_selected_armature_obj(context)

        self.armature_obj.data.VRCBTK.ensure_mappings()
         
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        
        # Show the bone mapping in the dialog
        if self.armature_obj.data and self.armature_obj.data.VRCBTK:
            for optional_mapping in self.armature_obj.data.VRCBTK.optional_map:
                row = layout.row()
                optional_mapping.draw(row)

            for category, humanoid_bones in HUMANOID_BONES_BY_CATEGORY.items():
                header_row = layout.row()
                header_row.label(text=str(category), icon='BONE_DATA')
                
                for humanoid_bone in humanoid_bones:
                    humanoid_bone_name = humanoid_bone["name"]
                    if optional_mapping := self.armature_obj.data.VRCBTK.get_optional_mapping(humanoid_bone_name):
                        if not optional_mapping.has:
                            continue

                    mappings_row = layout.row()
                    
                    bone_mapping = self.armature_obj.data.VRCBTK.get_mapping(humanoid_bone_name)
                    bone_mapping.draw(mappings_row)
                        
        
        layout.operator(VRCBTK_Operators_IdentifyHumanoidBones.bl_idname, icon="VIEWZOOM")
        layout.operator(VRCBTK_Operators_NormalizeHumanoidBones.bl_idname, icon="GREASEPENCIL")

    def execute(self, context):
        return {'FINISHED'}

    def cancel(self, context):
        print("Modal dialog was canceled.")
    
@registerme
class VRCBTK_Operators_NormalizeHumanoidBones(bpy.types.Operator):
    bl_idname = "vrcbtk.normalize_humanoid_bones"
    bl_label = "Normalize Humanoid Bone"
    bl_options = {'UNDO'}

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
        armature_obj: bpy.types.Armature = VRCBTK_PropertyGroups_SceneData.get_selected_armature_obj(context)

        for mapping in armature_obj.data.VRCBTK.bone_map:
            if mapping.armature_bone_name == "None":
                continue

            if "Humanoid" not in armature_obj.data.collections:
                humanoid_group = armature_obj.data.collections.new(name="Humanoid")
            else:
                humanoid_group = armature_obj.data.collections["Humanoid"]

            humanoid_bone = HUMANOID_BONE_DICT.get(mapping.humanoid_bone_name)

            # Select the armature object
            bpy.context.view_layer.objects.active = armature_obj

            bpy.ops.object.mode_set(mode='OBJECT')
            bone_candidates = [bone for bone in armature_obj.data.bones if bone.name == mapping.armature_bone_name]
            if len(bone_candidates) == 1:
                bone = bone_candidates[0]
                bone.name = mapping.humanoid_bone_name

            bpy.ops.object.mode_set(mode='EDIT')
            bone_candidates = [bone for bone in armature_obj.data.edit_bones if bone.name == mapping.armature_bone_name]
            if len(bone_candidates) == 1:
                bone: bpy.types.Bone = bone_candidates[0]
                bone.name = mapping.humanoid_bone_name

                if humanoid_bone["connected"]:
                    bone.parent.tail = bone.head
                    bone.use_connect = True

                humanoid_group.assign(bone)

                mapping.armature_bone_name = mapping.humanoid_bone_name

        return {'FINISHED'}

@registerme
class VRCBTK_Operators_IdentifyHumanoidBones(bpy.types.Operator):
    bl_idname = "vrcbtk.identify_humanoid_bones"
    bl_label = "Identify Humanoid Bones"
    bl_options = {'UNDO'}

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
        armature_obj: bpy.types.Object = VRCBTK_PropertyGroups_SceneData.get_selected_armature_obj(context)

        def get_bone_mapping(humanoid_bone_name: str):
            return [x for x in armature_obj.data.VRCBTK.bone_map if x.humanoid_bone_name == humanoid_bone_name][0]

        def set_bone_mapping(humanoid_bone_name: str, armature_bone_name: str):
            get_bone_mapping(humanoid_bone_name).armature_bone_name = armature_bone_name

        hips: bpy.types.Bone = armature_obj.data.bones[0]
        set_bone_mapping("Hips", hips.name)

        def get_child_bones_pointing_in_direction(bone: bpy.types.Bone, direction: mathutils.Vector, tolerance: float = 0.5) -> list[bpy.types.Bone]:
            def cond(b: bpy.types.Bone):
                # World space matrix of the bone
                bone_matrix_world = armature_obj.matrix_world @ b.matrix_local

                # Convert to vector and normalize
                bone_direction = bone_matrix_world.to_3x3() @ mathutils.Vector((0, 1, 0))

                dot_product = bone_direction.dot(direction)
                return dot_product > (1.0 - tolerance)
            return [c for c in bone.children if cond(bone)]
        
        left_bones = set([bone for bone in armature_obj.data.bones if bone.head.x > 0])
        right_bones = set([bone for bone in armature_obj.data.bones if bone.head.x < 0])
        
        spine: bpy.types.Bone | None = None
        chest: bpy.types.Bone | None = None
        upper_chest: bpy.types.Bone | None = None
        neck: bpy.types.Bone | None = None
        head: bpy.types.Bone | None = None

        def check_bone(humanoid_bone_name: str, candidates) -> tuple[bpy.types.Bone | None, bool]:
            humanoid_bone = HUMANOID_BONE_DICT.get(humanoid_bone_name)

            if optional_mapping := armature_obj.data.VRCBTK.get_optional_mapping(humanoid_bone_name):
                if not optional_mapping.has:
                    return (None, False)

            mapping = get_bone_mapping(humanoid_bone_name)
            if mapping.armature_bone_name != "None":
                return (armature_obj.data.bones[mapping.armature_bone_name], False)
            else:
                reduced_candidates = [candidate for candidate in candidates if any([keyword in candidate.name.lower() for keyword in humanoid_bone["keywords"]])]
                if len(reduced_candidates) > 0:
                    candidates = reduced_candidates

                if len(candidates) == 0:
                    return (None, False)
                if len(candidates) == 1:
                    bone = candidates[0]
                    set_bone_mapping(humanoid_bone_name, bone.name)
                    return (bone, False)
                else:
                    bpy.ops.vrcbtk.resolve_ambiguous_bone_modal(
                        'INVOKE_DEFAULT', 
                        armature_obj_name=armature_obj.name,
                        humanoid_bone_name=humanoid_bone_name,
                        armature_bone_names=[{"name": "", "armature_bone_name": bone.name} for bone in candidates],
                    )

                    return (None, True)

        (spine, exit) = check_bone(HumanoidBone.Spine, get_child_bones_pointing_in_direction(hips, direction=(0, 0, 1)))
        if exit: return {"PASS_THROUGH"}
        
        if spine:
            (chest, exit) = check_bone(HumanoidBone.Chest, get_child_bones_pointing_in_direction(spine, direction=(0, 0, 1)))
            if exit: return {"PASS_THROUGH"}

            if chest:
                (upper_chest, exit) = check_bone(HumanoidBone.UpperChest, get_child_bones_pointing_in_direction(chest, direction=(0, 0, 1)))
                if exit: return {"PASS_THROUGH"}

                if upper_chest:
                    parent_bone_for_neck = upper_chest
                else:
                    parent_bone_for_neck = chest

            if parent_bone_for_neck:
                (neck, exit) = check_bone("Neck", get_child_bones_pointing_in_direction(parent_bone_for_neck, direction=(0, 0, 1)))
                if exit: return {"PASS_THROUGH"}

                if neck:
                    (head, exit) = check_bone("Head", get_child_bones_pointing_in_direction(neck, direction=(0, 0, 1)))
                    if exit: return {"PASS_THROUGH"}
                    
                    if head:
                        (_, exit) = check_bone("LeftEye", left_bones.intersection(head.children))
                        if exit: return {"PASS_THROUGH"}

                        (_, exit) = check_bone("RightEye", right_bones.intersection(head.children))
                        if exit: return {"PASS_THROUGH"}

                        (_, exit) = check_bone("Jaw", head.children)
                        if exit: return {"PASS_THROUGH"}

                def arm(side: str, direction: mathutils.Vector):
                    (shoulder, exit) = check_bone(f"{side}Shoulder", get_child_bones_pointing_in_direction(parent_bone_for_neck, direction=direction))
                    if exit: return {"PASS_THROUGH"}

                    if shoulder:
                        (upper_arm, exit) = check_bone(f"{side}UpperArm", get_child_bones_pointing_in_direction(shoulder, direction=direction))
                        if exit: return {"PASS_THROUGH"}

                        if upper_arm:
                            (lower_arm, exit) = check_bone(f"{side}LowerArm", get_child_bones_pointing_in_direction(upper_arm, direction=direction))
                            if exit: return {"PASS_THROUGH"}

                            if lower_arm:
                                (hand, exit) = check_bone(f"{side}Hand", get_child_bones_pointing_in_direction(lower_arm, direction=direction))
                                if exit: return {"PASS_THROUGH"}

                                if hand:
                                    def finger(finger_name: str):
                                        proximal_candidates = get_child_bones_pointing_in_direction(hand, direction=direction)
                                        refined_candidates = [x for x in proximal_candidates if finger_name.lower() in x.name.lower()]
                                        if (len(refined_candidates) > 0):
                                            proximal_candidates = refined_candidates
                                        (proximal, exit) = check_bone(f"{side}{finger_name}Proximal", proximal_candidates)
                                        if exit: return {"PASS_THROUGH"}

                                        if proximal:
                                            (intermediate, exit) = check_bone(f"{side}{finger_name}Intermediate", get_child_bones_pointing_in_direction(proximal, direction=direction))
                                            if exit: return {"PASS_THROUGH"}

                                            if intermediate:
                                                (_, exit) = check_bone(f"{side}{finger_name}Distal", get_child_bones_pointing_in_direction(intermediate, direction=direction))
                                                if exit: return {"PASS_THROUGH"}
                                    
                                    if exit := finger("Little"):
                                        return exit
                                    if exit := finger("Ring"):
                                        return exit
                                    if exit := finger("Middle"):
                                        return exit
                                    if exit := finger("Index"):
                                        return exit
                                    if exit := finger("Thumb"):
                                        return exit
                                        
                if exit := arm("Left", (1, 0, 0)):
                    return exit
                if exit := arm("Right", (-1, 0, 0)):
                    return exit
                            
        upper_leg_candidates = get_child_bones_pointing_in_direction(hips, (0, 0, -1))

        def leg(side: str, bone_set: set):
            (upper_leg, exit) = check_bone(f"{side}UpperLeg", list(bone_set.intersection(upper_leg_candidates)))
            if exit: return {"PASS_THROUGH"}

            if upper_leg:
                (lower_leg, exit) = check_bone(f"{side}LowerLeg", get_child_bones_pointing_in_direction(upper_leg, (0, 0, -1)))
                if exit: return {"PASS_THROUGH"}

                if lower_leg:
                    (foot, exit) = check_bone(f"{side}Foot", get_child_bones_pointing_in_direction(lower_leg, (0, 0, -1), 0.8))
                    if exit: return {"PASS_THROUGH"}

                    if foot:
                        (_, exit) = check_bone(f"{side}Toes", foot.children)
                        if exit: return {"PASS_THROUGH"}
        
        if exit := leg("Left", left_bones):
            return exit
        if exit := leg("Right", right_bones):
            return exit

        return {'FINISHED'}

@registerme
class VRCBTK_PropertyGroups_ArmatureBoneName(bpy.types.PropertyGroup):
    @classmethod
    def register_me(cls):
        bpy.utils.register_class(cls)

    @classmethod
    def unregister_me(cls):
        bpy.utils.unregister_class(cls)

    armature_bone_name: bpy.props.StringProperty()

@registerme
class VRCBTK_Operators_ResolveAmbiguousBoneModal(bpy.types.Operator):
    bl_idname = "vrcbtk.resolve_ambiguous_bone_modal"
    bl_label = "Resolve ambiguous bone"
    bl_options = {"UNDO"}

    @classmethod
    def register_me(cls):
        bpy.utils.register_class(cls)

    @classmethod
    def unregister_me(cls):
        bpy.utils.unregister_class(cls)

    armature_obj_name: bpy.props.StringProperty()
    humanoid_bone_name: bpy.props.StringProperty()
    armature_bone_names: bpy.props.CollectionProperty(type=VRCBTK_PropertyGroups_ArmatureBoneName)
    armature_bone_name: bpy.props.EnumProperty(
        name="Bone",
        description="",
        items=lambda self, context: [
            (
                armature_bone_name,
                armature_bone_name,
                armature_bone_name,
                "",
                i,
            )
            for i, armature_bone_name in enumerate(sorted([x.armature_bone_name for x in self.armature_bone_names]))
        ]
    )

    def invoke(self, context, event=None):
        wm = context.window_manager
        print(self.armature_bone_names)
        return wm.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout

        layout.label(text=f"{self.humanoid_bone_name}:")
        layout.prop(self, "armature_bone_name", text="")

    def execute(self, context):
        armature = get_armature_by_object_name(context, self.armature_obj_name)
        
        armature.VRCBTK.get_mapping(self.humanoid_bone_name).armature_bone_name = self.armature_bone_name

        bpy.ops.vrcbtk.identify_humanoid_bones()

        return {'PASS_THROUGH'}