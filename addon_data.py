import bpy

from .util import registerme
from .typing_helpers import get_scene_data



@registerme
class VRCACTK_SceneData(bpy.types.PropertyGroup):
    @classmethod
    def register_me(cls) -> None:
        bpy.utils.register_class(cls)
        setattr(bpy.types.Scene, "VRCACTK", bpy.props.PointerProperty(type=cls))
    
    @classmethod
    def unregister_me(cls) -> None:
        if hasattr(bpy.types.Scene, "VRCACTK"):
            delattr(bpy.types.Scene, "VRCACTK")
        bpy.utils.unregister_class(cls)


    selected_armature_obj: bpy.props.PointerProperty(type=bpy.types.Object)

    def update_selected_armature(self, context: bpy.types.Context):
        scene = context.scene
        if scene is None:
            return
        scene_data = get_scene_data(context)
        scene_data.selected_armature_obj = scene.objects.get(self.armature_dropdown)

    armature_dropdown: bpy.props.EnumProperty(
        name="Armature",
        items=lambda _, context: [
            (obj.name, obj.name, "", "ARMATURE_DATA", i)
            for i, obj in enumerate((context.scene.objects if context is not None and context.scene is not None else []))
            if obj.type == 'ARMATURE'
        ],
        update=update_selected_armature,
    )


@registerme
class VRCACTK_ReportEvidence(bpy.types.PropertyGroup):
    @classmethod
    def register_me(cls) -> None:
        bpy.utils.register_class(cls)

    @classmethod
    def unregister_me(cls) -> None:
        bpy.utils.unregister_class(cls)

    key: bpy.props.StringProperty(name="Evidence Key", default="")
    label: bpy.props.StringProperty(name="Evidence Label", default="")


@registerme
class VRCACTK_ReportIssue(bpy.types.PropertyGroup):
    @classmethod
    def register_me(cls) -> None:
        bpy.utils.register_class(cls)

    @classmethod
    def unregister_me(cls) -> None:
        bpy.utils.unregister_class(cls)

    issue_type: bpy.props.EnumProperty(
        name="Issue Type",
        items=[
            ("DEGENERATE_GEOMETRY", "Degenerate Geometry", ""),
            ("LOOSE_GEOMETRY", "Loose Geometry", ""),
            ("UNWEIGHTED_VERTICES", "Unweighted Vertices", ""),
            ("UNUSED_SHAPE_KEY", "Unused Shape Key", ""),
            ("UNUSED_VERTEX_GROUP", "Unused Vertex Group", ""),
            ("UNUSED_MATERIAL_SLOT", "Unused Material Slot", ""),
            ("MULTIPLE_UV_MAPS", "Multiple UV Maps", ""),
            ("UNUSED_BONE", "Unused Bone", ""),
            ("UNCONNECTED_BONE_CHAIN", "Unconnected Bone Chain", ""),
            ("UNAPPLIED_TRANSFORMS", "Unapplied Transforms", ""),
            ("SHAPE_KEY_BASIS_MISMATCH", "Shape Key Basis Mismatch", ""),
        ],
    )
    category: bpy.props.StringProperty(name="Category", default="")
    description: bpy.props.StringProperty(name="Description", default="")
    target_object: bpy.props.PointerProperty(type=bpy.types.Object)
    object_name: bpy.props.StringProperty(name="Object Name", default="")
    item_name: bpy.props.StringProperty(name="Item Name", default="")
    slot_index: bpy.props.IntProperty(name="Slot Index", default=-1)
    evidence: bpy.props.CollectionProperty(type=VRCACTK_ReportEvidence)
    has_auto_fix: bpy.props.BoolProperty(name="Has Auto Fix", default=False)
    can_accept: bpy.props.BoolProperty(name="Can Accept as Intentional", default=True)
    do_fix: bpy.props.BoolProperty(name="Apply Auto Fix", default=False)


@registerme
class VRCACTK_ReportDecision(bpy.types.PropertyGroup):
    @classmethod
    def register_me(cls) -> None:
        bpy.utils.register_class(cls)

    @classmethod
    def unregister_me(cls) -> None:
        bpy.utils.unregister_class(cls)

    issue_type: bpy.props.StringProperty(name="Issue Type", default="")
    category: bpy.props.StringProperty(name="Category", default="")
    description: bpy.props.StringProperty(name="Description", default="")
    target_object: bpy.props.PointerProperty(type=bpy.types.Object)
    object_name: bpy.props.StringProperty(name="Object Name", default="")
    item_name: bpy.props.StringProperty(name="Item Name", default="")
    slot_index: bpy.props.IntProperty(name="Slot Index", default=-1)
    accepted_items: bpy.props.CollectionProperty(type=VRCACTK_ReportEvidence)
    note: bpy.props.StringProperty(name="Note", default="")
    is_active: bpy.props.BoolProperty(name="Currently Applies", default=False)


@registerme
class VRCACTK_ArmatureData(bpy.types.PropertyGroup):
    @classmethod
    def register_me(cls) -> None:
        bpy.utils.register_class(cls)
        setattr(bpy.types.Armature, "VRCACTK", bpy.props.PointerProperty(type=cls))
    
    @classmethod
    def unregister_me(cls) -> None:
        if hasattr(bpy.types.Armature, "VRCACTK"):
            delattr(bpy.types.Armature, "VRCACTK")
        bpy.utils.unregister_class(cls)

    def update_report_refresh(self, context: bpy.types.Context):
        if not self.report_refresh:
            return
        try:
            from . import util_operations
            util_operations._populate_report_issues(context)
        finally:
            self.report_refresh = False

    report_issues: bpy.props.CollectionProperty(type=VRCACTK_ReportIssue)
    report_decisions: bpy.props.CollectionProperty(type=VRCACTK_ReportDecision)
    report_issue_index: bpy.props.IntProperty(name="Report Issue Index", default=0)
    report_refresh: bpy.props.BoolProperty(
        name="Analyze Issues",
        default=False,
        update=update_report_refresh,
    )
    report_has_analysis: bpy.props.BoolProperty(
        name="Report Has Analysis",
        default=False,
    )
    report_expand_loose_geometry: bpy.props.BoolProperty(
        name="Loose Geometry",
        default=False,
    )
    report_expand_degenerate_geometry: bpy.props.BoolProperty(
        name="Degenerate Geometry",
        default=False,
    )
    report_expand_unused_shape_keys: bpy.props.BoolProperty(
        name="Unused Shape Keys",
        default=False,
    )
    report_expand_unused_vertex_groups: bpy.props.BoolProperty(
        name="Unused Vertex Groups",
        default=False,
    )
    report_expand_unused_material_slots: bpy.props.BoolProperty(
        name="Unused Material Slots",
        default=False,
    )
    report_expand_multiple_uv_maps: bpy.props.BoolProperty(
        name="Multiple UV Maps",
        default=False,
    )
    report_expand_unused_bones: bpy.props.BoolProperty(
        name="Unused Bones",
        default=False,
    )
    report_expand_unconnected_bone_chains: bpy.props.BoolProperty(
        name="Unconnected Bone Chains",
        default=False,
    )
    report_expand_unapplied_transforms: bpy.props.BoolProperty(
        name="Unapplied Transforms",
        default=False,
    )
    report_expand_shape_key_basis_mismatch: bpy.props.BoolProperty(
        name="Shape Key Basis Mismatch",
        default=False,
    )
    report_expand_unweighted_vertices: bpy.props.BoolProperty(
        name="Unweighted Vertices",
        default=False,
    )
    report_expand_accepted_decisions: bpy.props.BoolProperty(
        name="Accepted Decisions",
        default=False,
    )
