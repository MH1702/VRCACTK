from enum import StrEnum
from typing import TypeVar, cast, Protocol
import bpy

class HumanoidBone(StrEnum):
    Hips = "Hips"
    Spine = "Spine"
    Chest = "Chest"
    UpperChest = "UpperChest"
    Neck = "Neck"
    Head = "Head"
    LeftEye = "LeftEye"
    RightEye = "RightEye"
    Jaw = "Jaw"
    RightUpperLeg = "RightUpperLeg"
    RightLowerLeg = "RightLowerLeg"
    RightFoot = "RightFoot"
    RightToes = "RightToes"
    RightShoulder = "RightShoulder"
    RightUpperArm = "RightUpperArm"
    RightLowerArm = "RightLowerArm"
    RightHand = "RightHand"
    RightThumbProximal = "RightThumbProximal"
    RightThumbIntermediate = "RightThumbIntermediate"
    RightThumbDistal = "RightThumbDistal"
    RightIndexProximal = "RightIndexProximal"
    RightIndexIntermediate = "RightIndexIntermediate"
    RightIndexDistal = "RightIndexDistal"
    RightMiddleProximal = "RightMiddleProximal"
    RightMiddleIntermediate = "RightMiddleIntermediate"
    RightMiddleDistal = "RightMiddleDistal"
    RightRingProximal = "RightRingProximal"
    RightRingIntermediate = "RightRingIntermediate"
    RightRingDistal = "RightRingDistal"
    RightLittleProximal = "RightLittleProximal"
    RightLittleIntermediate = "RightLittleIntermediate"
    RightLittleDistal = "RightLittleDistal"
    LeftUpperLeg = "LeftUpperLeg"
    LeftLowerLeg = "LeftLowerLeg"
    LeftFoot = "LeftFoot"
    LeftToes = "LeftToes"
    LeftShoulder = "LeftShoulder"
    LeftUpperArm = "LeftUpperArm"
    LeftLowerArm = "LeftLowerArm"
    LeftHand = "LeftHand"
    LeftThumbProximal = "LeftThumbProximal"
    LeftThumbIntermediate = "LeftThumbIntermediate"
    LeftThumbDistal = "LeftThumbDistal"
    LeftIndexProximal = "LeftIndexProximal"
    LeftIndexIntermediate = "LeftIndexIntermediate"
    LeftIndexDistal = "LeftIndexDistal"
    LeftMiddleProximal = "LeftMiddleProximal"
    LeftMiddleIntermediate = "LeftMiddleIntermediate"
    LeftMiddleDistal = "LeftMiddleDistal"
    LeftRingProximal = "LeftRingProximal"
    LeftRingIntermediate = "LeftRingIntermediate"
    LeftRingDistal = "LeftRingDistal"
    LeftLittleProximal = "LeftLittleProximal"
    LeftLittleIntermediate = "LeftLittleIntermediate"
    LeftLittleDistal = "LeftLittleDistal"

    @classmethod
    def list(cls):
        return [e.value for e in cls]

class HumanoidBoneCategory(StrEnum):
    Body = "Body"
    Head = "Head"
    LeftLeg = "Left Leg"
    LeftArm = "Left Arm"
    LeftHand = "Left Hand"
    RightLeg = "Right Leg"
    RightArm = "Right Arm"
    RightHand = "Right Hand"

    @classmethod
    def list(cls):
        return [e.value for e in cls]

HUMANOID_BONE_DICT = {
    #region Body
    HumanoidBone.Hips: {
        "category": HumanoidBoneCategory.Body,
        "keywords": ["hips", "root"],
        "required": True,
        "connected": False,
        "path": "hips",
        "depth": 0,
    },
    HumanoidBone.Spine: {
        "category": HumanoidBoneCategory.Body,
        "keywords": ["spine"],
        "required": True,
        "connected": True,
        "path": "hips/axial",
        "depth": 0,
    },
    HumanoidBone.Chest: {
        "category": HumanoidBoneCategory.Body,
        "keywords": ["chest"],
        "required": False,
        "connected": True,
        "path": "hips/axial",
        "depth": 1,
    },
    HumanoidBone.UpperChest: {
        "category": HumanoidBoneCategory.Body,
        "keywords": ["chest"],
        "required": False,
        "connected": True,
        "path": "hips/axial",
        "depth": 2,
    },
    #endregion
    #region Head
    HumanoidBone.Neck: {
        "category": HumanoidBoneCategory.Head,
        "keywords": ["neck"],
        "required": False,
        "connected": False,
        "path": "hips/axial",
        "depth": 3,
    },
    HumanoidBone.Head: {
        "category": HumanoidBoneCategory.Head,
        "keywords": ["head"],
        "required": True,
        "connected": True,
        "path": "hips/axial",
        "depth": 4,
    },
    HumanoidBone.LeftEye: {
        "category": HumanoidBoneCategory.Head,
        "keywords": ["eye"],
        "required": False,
        "connected": False,
        "path": "hips/axial/left_eye",
        "depth": 0,
    },
    HumanoidBone.RightEye: {
        "category": HumanoidBoneCategory.Head,
        "keywords": ["eye"],
        "required": False,
        "connected": False,
        "path": "hips/axial/right_eye",
        "depth": 0,
    },
    HumanoidBone.Jaw: {
        "category": HumanoidBoneCategory.Head,
        "keywords": ["jaw","mouth"],
        "connected": False,
        "required": False,
        "path": "hips/axial/jaw",
        "depth": 0,
    },
    #endregion
    #region Right Leg
    HumanoidBone.RightUpperLeg: {
        "category": HumanoidBoneCategory.RightLeg,
        "keywords": ["leg"],
        "connected": False,
        "required": True,
        "path": "hips/axial/right_leg",
        "depth": 0,
    },
    HumanoidBone.RightLowerLeg: {
        "category": HumanoidBoneCategory.RightLeg,
        "keywords": ["leg","knee"],
        "required": True,
        "connected": True,
        "path": "hips/axial/right_leg",
        "depth": 1,
    },
    HumanoidBone.RightFoot: {
        "category": HumanoidBoneCategory.RightLeg,
        "keywords": ["foot","ankle"],
        "required": True,
        "connected": True,
        "path": "hips/axial/right_leg",
        "depth": 2,
    },
    HumanoidBone.RightToes: {
        "category": HumanoidBoneCategory.RightLeg,
        "keywords": ["toes"],
        "required": False,
        "connected": True,
        "path": "hips/axial/right_leg",
        "depth": 3,
    },
    #endregion
    #region Right Arm
    HumanoidBone.RightShoulder: {
        "category": HumanoidBoneCategory.RightArm,
        "keywords": ["shoulder"],
        "required": False,
        "connected": False,
        "path": "hips/axial/right_arm",
        "depth": 0,
    },
    HumanoidBone.RightUpperArm: {
        "category": HumanoidBoneCategory.RightArm,
        "keywords": ["arm"],
        "required": True,
        "connected": True,
        "path": "hips/axial/right_arm",
        "depth": 1,
    },
    HumanoidBone.RightLowerArm: {
        "category": HumanoidBoneCategory.RightArm,
        "keywords": ["arm","elbow"],
        "required": True,
        "connected": True,
        "path": "hips/axial/right_arm",
        "depth": 2,
    },
    HumanoidBone.RightHand: {
        "category": HumanoidBoneCategory.RightArm,
        "keywords": ["hand","wrist"],
        "required": True,
        "connected": True,
        "path": "hips/axial/right_arm",
        "depth": 2,
    },
    #endregion
    #region Right Hand
    HumanoidBone.RightThumbProximal: {
        "category": HumanoidBoneCategory.RightHand,
        "keywords": ["thumb"],
        "required": True,
        "connected": False,
        "path": "hips/axial/right_arm/thumb",
        "depth": 0,
    },
    HumanoidBone.RightThumbIntermediate: {
        "category": HumanoidBoneCategory.RightHand,
        "keywords": ["thumb"],
        "required": True,
        "connected": True,
        "path": "hips/axial/right_arm/thumb",
        "depth": 1,
    },
    HumanoidBone.RightThumbDistal: {
        "category": HumanoidBoneCategory.RightHand,
        "keywords": ["thumb"],
        "required": True,
        "connected": True,
        "path": "hips/axial/right_arm/thumb",
        "depth": 2,
    },
    HumanoidBone.RightIndexProximal: {
        "category": HumanoidBoneCategory.RightHand,
        "keywords": ["index","pointer"],
        "required": True,
        "connected": False,
        "path": "hips/axial/right_arm/index",
        "depth": 0,
    },
    HumanoidBone.RightIndexIntermediate: {
        "category": HumanoidBoneCategory.RightHand,
        "keywords": ["index","pointer"],
        "required": True,
        "connected": True,
        "path": "hips/axial/right_arm/index",
        "depth": 1,
    },
    HumanoidBone.RightIndexDistal: {
        "category": HumanoidBoneCategory.RightHand,
        "keywords": ["index","pointer"],
        "required": True,
        "connected": True,
        "path": "hips/axial/right_arm/index",
        "depth": 2,
    },
    HumanoidBone.RightMiddleProximal: {
        "category": HumanoidBoneCategory.RightHand,
        "keywords": ["middle"],
        "required": True,
        "connected": False,
        "path": "hips/axial/right_arm/middle",
        "depth": 0,
    },
    HumanoidBone.RightMiddleIntermediate: {
        "category": HumanoidBoneCategory.RightHand,
        "keywords": ["middle"],
        "required": True,
        "connected": True,
        "path": "hips/axial/right_arm/middle",
        "depth": 1,
    },
    HumanoidBone.RightMiddleDistal: {
        "category": HumanoidBoneCategory.RightHand,
        "keywords": ["middle"],
        "required": True,
        "connected": True,
        "path": "hips/axial/right_arm/middle",
        "depth": 2,
    },
    HumanoidBone.RightRingProximal: {
        "category": HumanoidBoneCategory.RightHand,
        "keywords": ["ring"],
        "required": True,
        "connected": False,
        "path": "hips/axial/right_arm/ring",
        "depth": 0,
    },
    HumanoidBone.RightRingIntermediate: {
        "category": HumanoidBoneCategory.RightHand,
        "keywords": ["ring"],
        "required": True,
        "connected": True,
        "path": "hips/axial/right_arm/ring",
        "depth": 1,
    },
    HumanoidBone.RightRingDistal: {
        "category": HumanoidBoneCategory.RightHand,
        "keywords": ["ring"],
        "required": True,
        "connected": True,
        "path": "hips/axial/right_arm/ring",
        "depth": 2,
    },
    HumanoidBone.RightLittleProximal: {
        "category": HumanoidBoneCategory.RightHand,
        "keywords": ["little","pinky"],
        "required": True,
        "connected": False,
        "path": "hips/axial/right_arm/little",
        "depth": 0,
    },
    HumanoidBone.RightLittleIntermediate: {
        "category": HumanoidBoneCategory.RightHand,
        "keywords": ["little","pinky"],
        "required": True,
        "connected": True,
        "path": "hips/axial/right_arm/little",
        "depth": 1,
    },
    HumanoidBone.RightLittleDistal: {
        "category": HumanoidBoneCategory.RightHand,
        "keywords": ["little","pinky"],
        "required": True,
        "connected": True,
        "path": "hips/axial/right_arm/little",
        "depth": 2,
    },
    #endregion
    #region Left Leg
    HumanoidBone.LeftUpperLeg: {
        "category": HumanoidBoneCategory.LeftLeg,
        "keywords": ["leg"],
        "connected": False,
        "required": True,
        "path": "hips/axial/left_leg",
        "depth": 0,
    },
    HumanoidBone.LeftLowerLeg: {
        "category": HumanoidBoneCategory.LeftLeg,
        "keywords": ["leg","knee"],
        "required": True,
        "connected": True,
        "path": "hips/axial/left_leg",
        "depth": 1,
    },
    HumanoidBone.LeftFoot: {
        "category": HumanoidBoneCategory.LeftLeg,
        "keywords": ["foot","ankle"],
        "required": True,
        "connected": True,
        "path": "hips/axial/left_leg",
        "depth": 2,
    },
    HumanoidBone.LeftToes: {
        "category": HumanoidBoneCategory.LeftLeg,
        "keywords": ["toes"],
        "required": False,
        "connected": True,
        "path": "hips/axial/left_leg",
        "depth": 3,
    },
    #endregion
    #region Left Arm
    HumanoidBone.LeftShoulder: {
        "category": HumanoidBoneCategory.LeftArm,
        "keywords": ["shoulder"],
        "required": False,
        "connected": False,
        "path": "hips/axial/left_arm",
        "depth": 0,
    },
    HumanoidBone.LeftUpperArm: {
        "category": HumanoidBoneCategory.LeftArm,
        "keywords": ["arm"],
        "required": True,
        "connected": True,
        "path": "hips/axial/left_arm",
        "depth": 1,
    },
    HumanoidBone.LeftLowerArm: {
        "category": HumanoidBoneCategory.LeftArm,
        "keywords": ["arm","elbow"],
        "required": True,
        "connected": True,
        "path": "hips/axial/left_arm",
        "depth": 2,
    },
    HumanoidBone.LeftHand: {
        "category": HumanoidBoneCategory.LeftArm,
        "keywords": ["hand","wrist"],
        "required": True,
        "connected": True,
        "path": "hips/axial/left_arm",
        "depth": 2,
    },
    #endregion
    #region Left Hand
    HumanoidBone.LeftThumbProximal: {
        "category": HumanoidBoneCategory.LeftHand,
        "keywords": ["thumb"],
        "required": True,
        "connected": False,
        "path": "hips/axial/left_arm/thumb",
        "depth": 0,
    },
    HumanoidBone.LeftThumbIntermediate: {
        "category": HumanoidBoneCategory.LeftHand,
        "keywords": ["thumb"],
        "required": True,
        "connected": True,
        "path": "hips/axial/left_arm/thumb",
        "depth": 1,
    },
    HumanoidBone.LeftThumbDistal: {
        "category": HumanoidBoneCategory.LeftHand,
        "keywords": ["thumb"],
        "required": True,
        "connected": True,
        "path": "hips/axial/left_arm/thumb",
        "depth": 2,
    },
    HumanoidBone.LeftIndexProximal: {
        "category": HumanoidBoneCategory.LeftHand,
        "keywords": ["index","pointer"],
        "required": True,
        "connected": False,
        "path": "hips/axial/left_arm/index",
        "depth": 0,
    },
    HumanoidBone.LeftIndexIntermediate: {
        "category": HumanoidBoneCategory.LeftHand,
        "keywords": ["index","pointer"],
        "required": True,
        "connected": True,
        "path": "hips/axial/left_arm/index",
        "depth": 1,
    },
    HumanoidBone.LeftIndexDistal: {
        "category": HumanoidBoneCategory.LeftHand,
        "keywords": ["index","pointer"],
        "required": True,
        "connected": True,
        "path": "hips/axial/left_arm/index",
        "depth": 2,
    },
    HumanoidBone.LeftMiddleProximal: {
        "category": HumanoidBoneCategory.LeftHand,
        "keywords": ["middle"],
        "required": True,
        "connected": False,
        "path": "hips/axial/left_arm/middle",
        "depth": 0,
    },
    HumanoidBone.LeftMiddleIntermediate: {
        "category": HumanoidBoneCategory.LeftHand,
        "keywords": ["middle"],
        "required": True,
        "connected": True,
        "path": "hips/axial/left_arm/middle",
        "depth": 1,
    },
    HumanoidBone.LeftMiddleDistal: {
        "category": HumanoidBoneCategory.LeftHand,
        "keywords": ["middle"],
        "required": True,
        "connected": True,
        "path": "hips/axial/left_arm/middle",
        "depth": 2,
    },
    HumanoidBone.LeftRingProximal: {
        "category": HumanoidBoneCategory.LeftHand,
        "keywords": ["ring"],
        "required": True,
        "connected": False,
        "path": "hips/axial/left_arm/ring",
        "depth": 0,
    },
    HumanoidBone.LeftRingIntermediate: {
        "category": HumanoidBoneCategory.LeftHand,
        "keywords": ["ring"],
        "required": True,
        "connected": True,
        "path": "hips/axial/left_arm/ring",
        "depth": 1,
    },
    HumanoidBone.LeftRingDistal: {
        "category": HumanoidBoneCategory.LeftHand,
        "keywords": ["ring"],
        "required": True,
        "connected": True,
        "path": "hips/axial/left_arm/ring",
        "depth": 2,
    },
    HumanoidBone.LeftLittleProximal: {
        "category": HumanoidBoneCategory.LeftHand,
        "keywords": ["little","pinky"],
        "required": True,
        "connected": False,
        "path": "hips/axial/left_arm/little",
        "depth": 0,
    },
    HumanoidBone.LeftLittleIntermediate: {
        "category": HumanoidBoneCategory.LeftHand,
        "keywords": ["little","pinky"],
        "required": True,
        "connected": True,
        "path": "hips/axial/left_arm/little",
        "depth": 1,
    },
    HumanoidBone.LeftLittleDistal: {
        "category": HumanoidBoneCategory.LeftHand,
        "keywords": ["little","pinky"],
        "required": True,
        "connected": True,
        "path": "hips/axial/left_arm/little",
        "depth": 2,
    },
    #endregion
}

HUMANOID_BONES_BY_CATEGORY = {
    HumanoidBoneCategory.Body: [
        {**bone, "name": name}
        for name, bone in HUMANOID_BONE_DICT.items()
        if bone["category"] == HumanoidBoneCategory.Body
    ],
    HumanoidBoneCategory.Head: [
        {**bone, "name": name}
        for name, bone in HUMANOID_BONE_DICT.items()
        if bone["category"] == HumanoidBoneCategory.Head
    ],
    HumanoidBoneCategory.LeftArm: [
        {**bone, "name": name}
        for name, bone in HUMANOID_BONE_DICT.items()
        if bone["category"] == HumanoidBoneCategory.LeftArm
    ],
    HumanoidBoneCategory.LeftHand: [
        {**bone, "name": name}
        for name, bone in HUMANOID_BONE_DICT.items()
        if bone["category"] == HumanoidBoneCategory.LeftHand
    ],
    HumanoidBoneCategory.LeftLeg: [
        {**bone, "name": name}
        for name, bone in HUMANOID_BONE_DICT.items()
        if bone["category"] == HumanoidBoneCategory.LeftLeg
    ],
    HumanoidBoneCategory.RightArm: [
        {**bone, "name": name}
        for name, bone in HUMANOID_BONE_DICT.items()
        if bone["category"] == HumanoidBoneCategory.RightArm
    ],
    HumanoidBoneCategory.RightHand: [
        {**bone, "name": name}
        for name, bone in HUMANOID_BONE_DICT.items()
        if bone["category"] == HumanoidBoneCategory.RightHand
    ],
    HumanoidBoneCategory.RightLeg: [
        {**bone, "name": name}
        for name, bone in HUMANOID_BONE_DICT.items()
        if bone["category"] == HumanoidBoneCategory.RightLeg
    ],
}


class Registerable(Protocol):
    def register_me(cls) -> None: ... # type: ignore
    def unregister_me(cls) -> None: ... # type: ignore

T = TypeVar("T", bound=type)

registry: dict[str, "Registerable"] = {}

def registerme(cls: T) -> T:
    registry.pop(cls.__name__, None)
    registry[cls.__name__] = cast("Registerable", cls)
    return cls


# def get_armature_by_object_name(context: bpy.types.Context, armature_obj_name: str) -> bpy.types.Armature | None:
#     if context is None or context.scene is None:
#         return None
#     obj = context.scene.objects.get(armature_obj_name)
#     if obj is None or obj.type != "ARMATURE":
#         return None
#     return obj.data
