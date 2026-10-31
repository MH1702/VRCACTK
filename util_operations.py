
import os
import struct
import unicodedata
from typing import TYPE_CHECKING, cast

import bpy
import bmesh
import numpy as np

from .typing_helpers import get_armature_obj, get_scene_data

from .addon_data import VRCACTK_SceneData as SceneData

from .util import registerme

if TYPE_CHECKING:
    from .addon_data import VRCACTK_ArmatureData as ArmatureData


_GEOMETRY_REPORT_ISSUE_TYPES = {
    "DEGENERATE_GEOMETRY",
    "LOOSE_GEOMETRY",
    "UNWEIGHTED_VERTICES",
}

_NON_ACCEPTABLE_REPORT_ISSUE_TYPES = {
    "DEGENERATE_GEOMETRY",
}


def _safe_filename(name: str) -> str:
    invalid = '<>:"/\\|?*'
    for ch in invalid:
        name = name.replace(ch, "_")
    return name.strip()


def _get_armature_data(context: bpy.types.Context) -> "ArmatureData | None":
    armature_obj = get_armature_obj(context)
    if armature_obj is None:
        return None
    return cast("ArmatureData", getattr(armature_obj.data, "VRCACTK"))


def _list_unused_vertex_groups(obj: bpy.types.Object) -> list[str]:
    if obj.type != "MESH":
        return []

    assert isinstance(obj.data, bpy.types.Mesh)

    names: list[str] = []
    for vg in obj.vertex_groups:
        group_index = vg.index
        group_used = False

        for vertex in obj.data.vertices:
            for group in vertex.groups:
                if group.group == group_index and group.weight > 1e-3:
                    group_used = True
                    break
            if group_used:
                break

        if not group_used:
            names.append(vg.name)

    return names


def _list_unused_shape_keys(obj: bpy.types.Object) -> list[str]:
    if obj.type != "MESH":
        return []

    assert isinstance(obj.data, bpy.types.Mesh)

    tolerance = 0.0001

    if not obj.data.shape_keys:
        return []

    kbs = obj.data.shape_keys.key_blocks

    nverts = len(obj.data.vertices)
    to_delete: list[str] = []

    cache: dict[str, np.ndarray] = {}

    locs = np.empty(3 * nverts, dtype=np.float32)

    for kb in kbs:
        if kb == kb.relative_key:
            continue
        if kb.name.startswith("vrc"):
            continue
        if kb.name.startswith("="):
            continue

        kb.data.foreach_get("co", locs)  # type: ignore

        if kb.relative_key.name not in cache:
            rel_locs = np.empty(3 * nverts, dtype=np.float32)
            kb.relative_key.data.foreach_get("co", rel_locs)  # type: ignore
            cache[kb.relative_key.name] = rel_locs
        rel_locs = cache[kb.relative_key.name]

        locs -= rel_locs
        if (np.abs(locs) < tolerance).all():
            if _looks_like_shape_key_separator(kb.name):
                continue
            to_delete.append(kb.name)

    return to_delete


def _looks_like_shape_key_separator(name: str) -> bool:
    """Heuristically identify decorative zero-delta shape-key headings.

    There is no standard separator syntax, so this deliberately recognizes
    decoration at either edge instead of relying on a fixed list of names.
    Callers must still verify that the shape key has no deformation.
    """
    stripped = name.strip()
    if not stripped:
        return False

    def is_decoration(character: str) -> bool:
        return not character.isalnum() and not character.isspace()

    leading_length = 0
    while (
        leading_length < len(stripped)
        and is_decoration(stripped[leading_length])
    ):
        leading_length += 1

    trailing_length = 0
    while (
        trailing_length < len(stripped) - leading_length
        and is_decoration(stripped[len(stripped) - trailing_length - 1])
    ):
        trailing_length += 1

    leading = stripped[:leading_length]
    trailing = stripped[len(stripped) - trailing_length:] if trailing_length else ""
    edge_decoration = leading + trailing
    if not edge_decoration:
        return False

    # Repeated/compound edge decoration can use arbitrary punctuation or symbols.
    if leading_length >= 2 or trailing_length >= 2:
        return True
    if leading_length and trailing_length:
        return True

    # A single edge character is only strong enough evidence when Unicode itself
    # describes it as a horizontal divider-like character.
    for character in edge_decoration:
        category = unicodedata.category(character)
        unicode_name = unicodedata.name(character, "")
        if category in {"Pd", "Pc"}:
            return True
        if any(
            marker in unicode_name
            for marker in (
                "HORIZONTAL",
                "DASH",
                "HYPHEN",
                "MINUS",
                "LOW LINE",
                "OVERLINE",
                "MACRON",
                "EQUALS",
                "TILDE",
            )
        ):
            return True
    return False


def _is_ignored_end_bone(bone: bpy.types.Bone) -> bool:
    """Return whether an unused leaf is conventionally named as an end bone."""
    if bone.children:
        return False

    base_name = bone.name
    stem, separator, suffix = base_name.rpartition(".")
    if separator and suffix.isdigit():
        base_name = stem
    return base_name.casefold().endswith("end")


def _list_unused_material_slots(obj: bpy.types.Object) -> list[tuple[int, str]]:
    if obj.type != "MESH":
        return []

    assert isinstance(obj.data, bpy.types.Mesh)

    polys = obj.data.polygons
    used_indices = {poly.material_index for poly in polys}

    unused: list[tuple[int, str]] = []
    materials = obj.data.materials
    for idx in range(len(materials)):
        if idx in used_indices:
            continue
        mat = materials[idx]
        mat_name = mat.name if mat is not None else ""
        unused.append((idx, mat_name))

    return unused


def _find_loose_geometry(obj: bpy.types.Object) -> tuple[int, int]:
    if obj.type != "MESH":
        return (0, 0)

    assert isinstance(obj.data, bpy.types.Mesh)

    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        loose_edges = sum(1 for e in bm.edges if len(e.link_faces) == 0)
        loose_verts = sum(1 for v in bm.verts if len(v.link_edges) == 0)
        return (loose_verts, loose_edges)
    finally:
        bm.free()


def _degenerate_geometry_elements(bm, *, edge_tol: float, face_area_tol: float):
    """Find tiny elements only where every stored shape key leaves vertices fixed.

    Use exact stored-coordinate comparisons: even a small shape-key delta can
    expand collapsed geometry, particularly with combined or extrapolated keys.
    BMesh shape layers also include inactive/muted keys and edit-mode changes.
    """
    shape_layers = list(bm.verts.layers.shape.values())
    moved_vertices = set()
    if len(shape_layers) > 1:
        basis_layer = shape_layers[0]
        moved_vertices = {
            vertex
            for vertex in bm.verts
            if any(
                vertex[layer] != vertex[basis_layer]
                for layer in shape_layers[1:]
            )
        }
    edges = [
        edge for edge in bm.edges
        if not any(vertex in moved_vertices for vertex in edge.verts)
        and edge.calc_length() <= edge_tol
    ]
    faces = [
        face for face in bm.faces
        if not any(vertex in moved_vertices for vertex in face.verts)
        and face.calc_area() <= face_area_tol
    ]
    return edges, faces


def _find_degenerate_geometry(
    obj: bpy.types.Object,
    *,
    edge_tol: float = 1e-6,
    face_area_tol: float = 1e-12,
) -> tuple[int, int]:
    if obj.type != "MESH":
        return (0, 0)

    assert isinstance(obj.data, bpy.types.Mesh)

    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        edges, faces = _degenerate_geometry_elements(
            bm, edge_tol=edge_tol, face_area_tol=face_area_tol
        )
        return (len(edges), len(faces))
    finally:
        bm.free()


def _find_unweighted_vertices(
    obj: bpy.types.Object,
    armature_obj: bpy.types.Object,
    *,
    weight_threshold: float = 1e-6,
) -> list[int]:
    if obj.type != "MESH" or armature_obj.type != "ARMATURE":
        return []

    assert isinstance(obj.data, bpy.types.Mesh)

    bone_names = {bone.name for bone in armature_obj.data.bones}
    bone_group_indices = {
        group.index
        for group in obj.vertex_groups
        if group.name in bone_names
    }
    return [
        vertex.index
        for vertex in obj.data.vertices
        if not any(
            assignment.group in bone_group_indices
            and assignment.weight > weight_threshold
            for assignment in vertex.groups
        )
    ]


def _summarize_indices(indices: list[int], label: str) -> str:
    preview = ", ".join(str(index) for index in indices[:20])
    if len(indices) > 20:
        preview += f" (+{len(indices) - 20} more)"
    return f"{label}: {preview}"


def _remove_loose_geometry(obj: bpy.types.Object) -> tuple[int, int]:
    if obj.type != "MESH":
        return (0, 0)

    assert isinstance(obj.data, bpy.types.Mesh)

    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        loose_edges = [e for e in bm.edges if len(e.link_faces) == 0]
        loose_verts = [v for v in bm.verts if len(v.link_edges) == 0]
        removed_edges = len(loose_edges)
        removed_verts = len(loose_verts)
        if loose_edges:
            bmesh.ops.delete(bm, geom=loose_edges, context="EDGES")
        if loose_verts:
            bmesh.ops.delete(bm, geom=loose_verts, context="VERTS")
        bm.to_mesh(obj.data)
        return (removed_verts, removed_edges)
    finally:
        bm.free()


def _list_multiple_uv_maps(obj: bpy.types.Object) -> list[str]:
    if obj.type != "MESH":
        return []

    assert isinstance(obj.data, bpy.types.Mesh)

    uv_layers = obj.data.uv_layers
    if len(uv_layers) <= 1:
        return []
    return [uv.name for uv in uv_layers]


def _find_unconnected_bone_chains(
    armature_obj: bpy.types.Object,
    *,
    tolerance: float = 1e-6,
) -> list[list[str]]:
    """Return linear runs whose parent tails do not meet their only child."""
    if armature_obj.type != "ARMATURE":
        return []

    bones = list(armature_obj.data.bones)
    unconnected = {
        bone.name
        for bone in bones
        if len(bone.children) == 1
        and (bone.tail_local - bone.children[0].head_local).length > tolerance
    }
    if not unconnected:
        return []

    chains: list[list[str]] = []
    visited: set[str] = set()
    for bone in bones:
        if bone.name not in unconnected or bone.name in visited:
            continue
        if bone.parent is not None and bone.parent.name in unconnected:
            continue

        chain: list[str] = []
        current = bone
        while current.name in unconnected and current.name not in visited:
            visited.add(current.name)
            chain.append(current.name)
            current = current.children[0]
        chains.append(chain)

    # Defensive fallback for malformed/cyclic data, even though Blender armatures
    # normally guarantee an acyclic hierarchy.
    for bone in bones:
        if bone.name in unconnected and bone.name not in visited:
            chains.append([bone.name])
    return chains


def _find_ambiguous_unconnected_bones(
    armature_obj: bpy.types.Object,
    *,
    tolerance: float = 1e-6,
) -> list[str]:
    """Return multi-child bones whose tail does not meet any child head."""
    if armature_obj.type != "ARMATURE":
        return []

    return [
        bone.name
        for bone in armature_obj.data.bones
        if len(bone.children) > 1
        and all(
            (bone.tail_local - child.head_local).length > tolerance
            for child in bone.children
        )
    ]


def _align_bone_tails(
    context: bpy.types.Context,
    armature_obj: bpy.types.Object,
    child_by_parent: dict[str, str],
) -> int:
    """Align requested parent tails to explicitly selected immediate children."""
    if armature_obj.type != "ARMATURE" or not child_by_parent:
        return 0

    eligible: dict[str, str] = {}
    for parent_name, child_name in child_by_parent.items():
        bone = armature_obj.data.bones.get(parent_name)
        child = armature_obj.data.bones.get(child_name)
        if bone is None or child is None or child.parent != bone:
            continue
        if (bone.tail_local - child.head_local).length <= 1e-6:
            continue
        eligible[parent_name] = child_name
    if not eligible:
        return 0

    view_layer = context.view_layer
    previous_active = view_layer.objects.active
    was_selected = armature_obj.select_get()
    try:
        armature_obj.select_set(True)
        view_layer.objects.active = armature_obj
        bpy.ops.object.mode_set(mode="EDIT")
        aligned = 0
        for parent_name, child_name in eligible.items():
            edit_bone = armature_obj.data.edit_bones.get(parent_name)
            edit_child = armature_obj.data.edit_bones.get(child_name)
            if (
                edit_bone is None
                or edit_child is None
                or edit_child.parent != edit_bone
            ):
                continue
            edit_bone.tail = edit_child.head.copy()
            aligned += 1
        bpy.ops.object.mode_set(mode="OBJECT")
        return aligned
    finally:
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        if not was_selected:
            armature_obj.select_set(False)
        view_layer.objects.active = previous_active


def _align_unconnected_bones(
    context: bpy.types.Context,
    armature_obj: bpy.types.Object,
    bone_names: set[str],
) -> int:
    """Align each requested parent tail to its sole child's head."""
    if armature_obj.type != "ARMATURE" or not bone_names:
        return 0

    child_by_parent = {
        bone.name: bone.children[0].name
        for bone in armature_obj.data.bones
        if bone.name in bone_names
        and len(bone.children) == 1
        and (bone.tail_local - bone.children[0].head_local).length > 1e-6
    }
    return _align_bone_tails(context, armature_obj, child_by_parent)


def _add_report_issue(
    armature_data: "ArmatureData",
    *,
    issue_type: str,
    category: str,
    description: str,
    target_object: bpy.types.Object,
    item_name: str = "",
    slot_index: int = -1,
    has_auto_fix: bool = False,
    evidence: list[tuple[str, str]] | None = None,
) -> None:
    issue = armature_data.report_issues.add()
    issue.issue_type = issue_type
    issue.category = category
    issue.description = description
    issue.target_object = target_object
    issue.object_name = target_object.name
    issue.item_name = item_name
    issue.slot_index = slot_index
    issue.has_auto_fix = has_auto_fix
    issue.can_accept = issue_type not in _NON_ACCEPTABLE_REPORT_ISSUE_TYPES
    issue.do_fix = False

    evidence_items = evidence
    if evidence_items is None:
        key = item_name or description
        evidence_items = [(key, item_name or description)]
    for key, label in evidence_items:
        item = issue.evidence.add()
        item.key = key
        item.label = label


def _evidence_keys(items) -> tuple[str, ...]:
    return tuple(sorted(item.key for item in items))


def _decision_matches_issue(decision, issue) -> bool:
    if issue.issue_type in _NON_ACCEPTABLE_REPORT_ISSUE_TYPES:
        return False
    return (
        decision.issue_type == issue.issue_type
        and decision.target_object == issue.target_object
        and _evidence_keys(decision.accepted_items) == _evidence_keys(issue.evidence)
    )


def _find_matching_decision(armature_data: "ArmatureData", issue):
    return next(
        (
            decision
            for decision in armature_data.report_decisions
            if _decision_matches_issue(decision, issue)
        ),
        None,
    )


def _get_unresolved_report_issues(context: bpy.types.Context) -> list:
    armature_data = _get_armature_data(context)
    if armature_data is None:
        return []
    return [
        issue
        for issue in armature_data.report_issues
        if _find_matching_decision(armature_data, issue) is None
    ]


def _refresh_decision_activity(armature_data: "ArmatureData") -> None:
    for decision in armature_data.report_decisions:
        matching_issue = next(
            (
                issue
                for issue in armature_data.report_issues
                if _decision_matches_issue(decision, issue)
            ),
            None,
        )
        decision.is_active = matching_issue is not None
        if matching_issue is not None:
            decision.category = matching_issue.category
            decision.description = matching_issue.description
            decision.object_name = matching_issue.object_name


def _scope_matches(
    issue_type: str,
    target_object: bpy.types.Object,
    issue_types: set[str] | None,
    target_objects: set[bpy.types.Object] | None,
) -> bool:
    return (
        (issue_types is None or issue_type in issue_types)
        and (target_objects is None or target_object in target_objects)
    )


def _populate_report_issues(
    context: bpy.types.Context,
    *,
    issue_types: set[str] | None = None,
    target_objects: set[bpy.types.Object] | None = None,
) -> bool:
    if context is None or context.scene is None:
        return False

    armature_obj = get_armature_obj(context)
    if armature_obj is None:
        return False

    armature_data = _get_armature_data(context)
    if armature_data is None:
        return False

    is_full_analysis = issue_types is None and target_objects is None
    if is_full_analysis:
        armature_data.report_issues.clear()
        armature_data.report_issue_index = 0
    else:
        for index in range(len(armature_data.report_issues) - 1, -1, -1):
            issue = armature_data.report_issues[index]
            if _scope_matches(
                issue.issue_type,
                issue.target_object,
                issue_types,
                target_objects,
            ):
                armature_data.report_issues.remove(index)
    armature_data.report_has_analysis = True
    for decision in armature_data.report_decisions:
        decision.is_active = False

    scene = context.scene
    if scene is None:
        return False

    meshes: list[bpy.types.Object] = []
    seen: set[str] = set()

    for obj in armature_obj.children_recursive:
        if obj.type != "MESH":
            continue
        if obj.name in seen:
            continue
        seen.add(obj.name)
        meshes.append(obj)

    for obj in scene.objects:
        if obj.type != "MESH":
            continue
        if obj.name in seen:
            continue
        for modifier in obj.modifiers:
            if modifier.type != "ARMATURE":
                continue
            if modifier.object == armature_obj:
                seen.add(obj.name)
                meshes.append(obj)
                break

    for obj in meshes:
        if _scope_matches(
            "DEGENERATE_GEOMETRY",
            obj,
            issue_types,
            target_objects,
        ):
            degenerate_edges, zero_area_faces = _find_degenerate_geometry(obj)
        else:
            degenerate_edges, zero_area_faces = (0, 0)
        if degenerate_edges or zero_area_faces:
            _add_report_issue(
                armature_data,
                issue_type="DEGENERATE_GEOMETRY",
                category="Degenerate Geometry",
                description=(
                    f"{degenerate_edges} zero-length edges, "
                    f"{zero_area_faces} zero-area faces on mesh '{obj.name}'"
                ),
                target_object=obj,
                has_auto_fix=False,
                evidence=[
                    (
                        f"degenerate_edges:{degenerate_edges}",
                        f"{degenerate_edges} zero-length edges",
                    ),
                    (
                        f"zero_area_faces:{zero_area_faces}",
                        f"{zero_area_faces} zero-area faces",
                    ),
                ],
            )

        if _scope_matches(
            "UNWEIGHTED_VERTICES",
            obj,
            issue_types,
            target_objects,
        ):
            unweighted_vertices = _find_unweighted_vertices(obj, armature_obj)
        else:
            unweighted_vertices = []
        if unweighted_vertices:
            vertex_text = ",".join(str(index) for index in unweighted_vertices)
            _add_report_issue(
                armature_data,
                issue_type="UNWEIGHTED_VERTICES",
                category="Unweighted Vertices",
                description=(
                    f"{len(unweighted_vertices)} vertices have no weights for "
                    f"armature '{armature_obj.name}' on mesh '{obj.name}'"
                ),
                target_object=obj,
                has_auto_fix=False,
                evidence=[
                    (
                        f"vertices:{vertex_text}",
                        _summarize_indices(unweighted_vertices, "Vertex indices"),
                    )
                ],
            )

        unused_shape_keys = (
            _list_unused_shape_keys(obj)
            if _scope_matches(
                "UNUSED_SHAPE_KEY",
                obj,
                issue_types,
                target_objects,
            )
            else []
        )
        for name in unused_shape_keys:
            _add_report_issue(
                armature_data,
                issue_type="UNUSED_SHAPE_KEY",
                category="Unused Shape Keys",
                description=f"Unused shape key '{name}' on mesh '{obj.name}'",
                target_object=obj,
                item_name=name,
                has_auto_fix=True,
                evidence=[(name, name)],
            )

        unused_vertex_groups = (
            _list_unused_vertex_groups(obj)
            if _scope_matches(
                "UNUSED_VERTEX_GROUP",
                obj,
                issue_types,
                target_objects,
            )
            else []
        )
        for name in unused_vertex_groups:
            _add_report_issue(
                armature_data,
                issue_type="UNUSED_VERTEX_GROUP",
                category="Unused Vertex Groups",
                description=f"Unused vertex group '{name}' on mesh '{obj.name}'",
                target_object=obj,
                item_name=name,
                has_auto_fix=True,
                evidence=[(name, name)],
            )

        unused_material_slots = (
            _list_unused_material_slots(obj)
            if _scope_matches(
                "UNUSED_MATERIAL_SLOT",
                obj,
                issue_types,
                target_objects,
            )
            else []
        )
        for idx, mat_name in unused_material_slots:
            label = f"Unused material slot {idx}"
            if mat_name:
                label += f" ('{mat_name}')"
            label += f" on mesh '{obj.name}'"
            _add_report_issue(
                armature_data,
                issue_type="UNUSED_MATERIAL_SLOT",
                category="Unused Material Slots",
                description=label,
                target_object=obj,
                item_name=mat_name,
                slot_index=idx,
                has_auto_fix=True,
                evidence=[(f"{idx}:{mat_name}", mat_name or f"Slot {idx}")],
            )

        if _scope_matches(
            "LOOSE_GEOMETRY",
            obj,
            issue_types,
            target_objects,
        ):
            loose_verts, loose_edges = _find_loose_geometry(obj)
        else:
            loose_verts, loose_edges = (0, 0)
        if loose_verts or loose_edges:
            _add_report_issue(
                armature_data,
                issue_type="LOOSE_GEOMETRY",
                category="Loose Geometry",
                description=(
                    f"Loose geometry ({loose_verts} loose verts, "
                    f"{loose_edges} loose edges) on mesh '{obj.name}'"
                ),
                target_object=obj,
                has_auto_fix=True,
                evidence=[
                    (
                        f"loose_vertices:{loose_verts}",
                        f"{loose_verts} loose vertices",
                    ),
                    (
                        f"loose_edges:{loose_edges}",
                        f"{loose_edges} loose edges",
                    ),
                ],
            )

        uv_names = (
            _list_multiple_uv_maps(obj)
            if _scope_matches(
                "MULTIPLE_UV_MAPS",
                obj,
                issue_types,
                target_objects,
            )
            else []
        )
        if uv_names:
            _add_report_issue(
                armature_data,
                issue_type="MULTIPLE_UV_MAPS",
                category="Multiple UV Maps",
                description=(
                    f"Multiple UV maps on mesh '{obj.name}': "
                    f"{', '.join(uv_names)}"
                ),
                target_object=obj,
                has_auto_fix=False,
                evidence=[(name, name) for name in uv_names],
            )

        if (
            _scope_matches(
                "SHAPE_KEY_BASIS_MISMATCH",
                obj,
                issue_types,
                target_objects,
            )
            and obj.data.shape_keys
        ):
            kbs = obj.data.shape_keys.key_blocks
            has_basis = any(kb.name == "Basis" for kb in kbs)
            if not has_basis or kbs[0].name != "Basis":
                desc = f"Shape key basis mismatch on mesh '{obj.name}'"
                if not has_basis:
                    desc += " (missing Basis key)"
                else:
                    desc += f" (first key is '{kbs[0].name}')"
                _add_report_issue(
                    armature_data,
                    issue_type="SHAPE_KEY_BASIS_MISMATCH",
                    category="Shape Key Basis Mismatch",
                    description=desc,
                    target_object=obj,
                    item_name="Basis",
                    has_auto_fix=False,
                    evidence=[
                        (
                            f"shape_key_order:{'|'.join(kb.name for kb in kbs)}",
                            "Shape keys: " + ", ".join(kb.name for kb in kbs),
                        )
                    ],
                )

        transform_flags = []
        if _scope_matches(
            "UNAPPLIED_TRANSFORMS",
            obj,
            issue_types,
            target_objects,
        ):
            if any(abs(v) > 1e-6 for v in obj.location):
                transform_flags.append("location")
            if obj.rotation_mode == "QUATERNION":
                rot = obj.rotation_quaternion
                if (
                    abs(rot.w - 1.0) > 1e-6
                    or abs(rot.x) > 1e-6
                    or abs(rot.y) > 1e-6
                    or abs(rot.z) > 1e-6
                ):
                    transform_flags.append("rotation")
            elif obj.rotation_mode == "AXIS_ANGLE":
                axis_angle = obj.rotation_axis_angle
                if abs(axis_angle[0]) > 1e-6:
                    transform_flags.append("rotation")
            else:
                if any(abs(v) > 1e-6 for v in obj.rotation_euler):
                    transform_flags.append("rotation")
            if any(abs(v - 1.0) > 1e-6 for v in obj.scale):
                transform_flags.append("scale")

        if transform_flags:
            transform_evidence: list[tuple[str, str]] = []
            for flag in transform_flags:
                if flag == "location":
                    values = obj.location
                elif flag == "scale":
                    values = obj.scale
                elif obj.rotation_mode == "QUATERNION":
                    values = obj.rotation_quaternion
                elif obj.rotation_mode == "AXIS_ANGLE":
                    values = obj.rotation_axis_angle
                else:
                    values = obj.rotation_euler
                value_text = ",".join(f"{value:.6g}" for value in values)
                transform_evidence.append(
                    (
                        f"{flag}:{value_text}",
                        f"{flag.title()}: {value_text}",
                    )
                )

            _add_report_issue(
                armature_data,
                issue_type="UNAPPLIED_TRANSFORMS",
                category="Unapplied Transforms",
                description=(
                    f"Unapplied transforms ({', '.join(transform_flags)}) "
                    f"on mesh '{obj.name}'"
                ),
                target_object=obj,
                has_auto_fix=False,
                evidence=transform_evidence,
            )

    if _scope_matches(
        "UNUSED_BONE",
        armature_obj,
        issue_types,
        target_objects,
    ):
        used_bone_names: set[str] = set()
        for obj in meshes:
            if obj.type != "MESH":
                continue
            for v in obj.data.vertices:
                for group in v.groups:
                    if group.weight <= 1e-3:
                        continue
                    if group.group < 0 or group.group >= len(obj.vertex_groups):
                        continue
                    vg = obj.vertex_groups[group.group]
                    used_bone_names.add(vg.name)

        bones = list(armature_obj.data.bones)
        used_or_desc: dict[str, bool] = {
            bone.name: bone.name in used_bone_names for bone in bones
        }
        children_map: dict[str, list[bpy.types.Bone]] = {
            bone.name: list(bone.children) for bone in bones
        }

        def _mark_used_desc(bone: bpy.types.Bone) -> bool:
            if used_or_desc[bone.name]:
                return True
            for child in children_map.get(bone.name, []):
                if _mark_used_desc(child):
                    used_or_desc[bone.name] = True
                    return True
            return False

        for bone in bones:
            _mark_used_desc(bone)

        unused_set = {
            bone.name
            for bone in bones
            if not used_or_desc[bone.name] and not _is_ignored_end_bone(bone)
        }
        visited: set[str] = set()

        for bone in bones:
            if bone.name not in unused_set or bone.name in visited:
                continue
            chain = []
            stack = [bone]
            while stack:
                current = stack.pop()
                if current.name in visited or current.name not in unused_set:
                    continue
                visited.add(current.name)
                chain.append(current.name)
                for child in current.children:
                    if child.name in unused_set and child.name not in visited:
                        stack.append(child)

            if chain:
                chain_display = " -> ".join(chain[:6])
                if len(chain) > 6:
                    chain_display += f" (+{len(chain) - 6} more)"
                _add_report_issue(
                    armature_data,
                    issue_type="UNUSED_BONE",
                    category="Unused Bones",
                    description=(
                        f"Unused bone chain ({len(chain)}) on armature "
                        f"'{armature_obj.name}':\n{chain_display}"
                    ),
                    target_object=armature_obj,
                    item_name=chain[0],
                    has_auto_fix=False,
                    evidence=[(name, name) for name in chain],
                )

    if _scope_matches(
        "UNCONNECTED_BONE_CHAIN",
        armature_obj,
        issue_types,
        target_objects,
    ):
        bones_by_name = {
            bone.name: bone for bone in armature_obj.data.bones
        }
        for chain in _find_unconnected_bone_chains(armature_obj):
            path = list(chain)
            last_bone = bones_by_name[chain[-1]]
            if len(last_bone.children) == 1:
                path.append(last_bone.children[0].name)
            path_display = " -> ".join(path[:7])
            if len(path) > 7:
                path_display += f" (+{len(path) - 7} more)"
            _add_report_issue(
                armature_data,
                issue_type="UNCONNECTED_BONE_CHAIN",
                category="Unconnected Bone Chains",
                description=(
                    f"Unconnected bone chain ({len(chain)}) on armature "
                    f"'{armature_obj.name}':\n{path_display}"
                ),
                target_object=armature_obj,
                item_name=chain[0],
                has_auto_fix=True,
                evidence=[
                    (
                        name,
                        f"{name} -> {bones_by_name[name].children[0].name}",
                    )
                    for name in chain
                ],
            )

        for bone_name in _find_ambiguous_unconnected_bones(armature_obj):
            bone = bones_by_name[bone_name]
            _add_report_issue(
                armature_data,
                issue_type="UNCONNECTED_BONE_CHAIN",
                category="Unconnected Bone Chains",
                description=(
                    f"Bone '{bone_name}' on armature '{armature_obj.name}' has "
                    f"{len(bone.children)} possible child connections. Choose "
                    "which child its tail should align to."
                ),
                target_object=armature_obj,
                item_name=bone_name,
                has_auto_fix=False,
                evidence=[
                    (child.name, child.name)
                    for child in bone.children
                ],
            )

    _refresh_decision_activity(armature_data)
    return True


def _apply_selected_fixes(context: bpy.types.Context) -> bool:
    if context is None or context.scene is None:
        return False

    armature_data = _get_armature_data(context)
    if armature_data is None:
        return False

    scene = context.scene
    if scene is None:
        return False

    issues_by_obj: dict[str, list[bpy.types.PropertyGroup]] = {}
    for issue in armature_data.report_issues:
        if not issue.has_auto_fix or not issue.do_fix:
            continue
        if _find_matching_decision(armature_data, issue) is not None:
            continue
        issues_by_obj.setdefault(issue.object_name, []).append(issue)

    for obj_name, issues in issues_by_obj.items():
        obj = scene.objects.get(obj_name)
        if obj is None:
            continue

        if obj.type == "ARMATURE":
            unconnected_bone_names = {
                evidence.key
                for issue in issues
                if issue.issue_type == "UNCONNECTED_BONE_CHAIN"
                for evidence in issue.evidence
            }
            _align_unconnected_bones(context, obj, unconnected_bone_names)
            continue

        if obj.type != "MESH":
            continue

        shape_keys_to_remove = [
            issue.item_name
            for issue in issues
            if issue.issue_type == "UNUSED_SHAPE_KEY"
        ]
        if shape_keys_to_remove:
            unused = set(_list_unused_shape_keys(obj))
            for name in shape_keys_to_remove:
                if name not in unused:
                    continue
                obj.shape_key_remove(obj.data.shape_keys.key_blocks[name])

        vertex_groups_to_remove = [
            issue.item_name
            for issue in issues
            if issue.issue_type == "UNUSED_VERTEX_GROUP"
        ]
        if vertex_groups_to_remove:
            unused = set(_list_unused_vertex_groups(obj))
            for name in vertex_groups_to_remove:
                if name not in unused:
                    continue
                vg = obj.vertex_groups.get(name)
                if vg is not None:
                    obj.vertex_groups.remove(vg)

        material_slot_indices = [
            issue.slot_index
            for issue in issues
            if issue.issue_type == "UNUSED_MATERIAL_SLOT"
        ]
        if material_slot_indices:
            material_slot_indices = sorted(set(material_slot_indices), reverse=True)
            unused_indices = {idx for idx, _ in _list_unused_material_slots(obj)}
            for idx in material_slot_indices:
                if idx not in unused_indices:
                    continue
                if idx < 0 or idx >= len(obj.data.materials):
                    continue
                obj.data.materials.pop(index=idx)

        if any(issue.issue_type == "LOOSE_GEOMETRY" for issue in issues):
            _remove_loose_geometry(obj)

    return True


@registerme
class VRCACTK_OT_RemoveUnusedVertexGroupsOperator(bpy.types.Operator):
    bl_idname = "vrcactk.remove_unused_vertex_groups_operator"
    bl_label = "Remove Unused Vertex Groups"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def register_me(cls):
        bpy.utils.register_class(cls)

    @classmethod
    def unregister_me(cls):
        bpy.utils.unregister_class(cls)
    
    
    def execute(self, context):
        if context is None:
            return {'CANCELLED'}
        if context.scene is None:
            return {'CANCELLED'}
        
        armature_obj = get_armature_obj(context)
        if armature_obj is None:
            return {'CANCELLED'}

        try:
            c = 0
            for obj in armature_obj.children_recursive:
                if obj.type != "MESH":
                    continue
                c += self.remove_unused_vertex_groups(obj)
            self.report({'INFO'}, f"Removed {c} unused vertex groups.")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to remove unused shape keys: {e}")
            return {'CANCELLED'}
        
    def remove_unused_vertex_groups(self, obj: bpy.types.Object) -> int:
        if obj.type != "MESH":
            return 0
        
        assert isinstance(obj.data, bpy.types.Mesh)

        names = _list_unused_vertex_groups(obj)
        removed = 0
        for name in names:
            vg = obj.vertex_groups.get(name)
            if vg is None:
                continue
            obj.vertex_groups.remove(vg)
            removed += 1

        self.report({'INFO'}, f"Removed {removed} unused vertex groups from '{obj.name}'. {names}")
        return removed

@registerme
class VRCACTK_OT_RemoveUnusedShapeKeysOperator(bpy.types.Operator):
    bl_idname = "vrcactk.remove_unused_shape_keys_operator"
    bl_label = "Remove Unused Shape Keys"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def register_me(cls):
        bpy.utils.register_class(cls)

    @classmethod
    def unregister_me(cls):
        bpy.utils.unregister_class(cls)

    def execute(self, context):
        if context is None:
            return {'CANCELLED'}
        if context.scene is None:
            return {'CANCELLED'}
        
        armature_obj = get_armature_obj(context)
        if armature_obj is None:
            return {'CANCELLED'}

        try:
            c = 0
            for obj in armature_obj.children_recursive:
                if obj.type != "MESH":
                    continue
                c += self.remove_unused_shape_keys(obj)
            self.report({'INFO'}, f"Removed {c} unused shape keys.")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to remove unused shape keys: {e}")
            return {'CANCELLED'}

    def remove_unused_shape_keys(self, obj: bpy.types.Object) -> int:
        if obj.type != "MESH":
            return 0
        
        assert isinstance(obj.data, bpy.types.Mesh)

        to_delete = _list_unused_shape_keys(obj)
        removed = 0

        for kb_name in to_delete:
            removed += 1
            obj.shape_key_remove(obj.data.shape_keys.key_blocks[kb_name])

        self.report({'INFO'}, f"Removed {removed} unused shape keys from '{obj.name}'. {to_delete}")
        return removed
    
@registerme
class VRCACTK_OT_RemoveUnusedMaterialSlotsOperator(bpy.types.Operator):
    bl_idname = "vrcactk.remove_unused_material_slots_operator"
    bl_label = "Remove Unused Material Slots"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def register_me(cls):
        bpy.utils.register_class(cls)

    @classmethod
    def unregister_me(cls):
        bpy.utils.unregister_class(cls)

    def execute(self, context):
        if context is None:
            return {'CANCELLED'}
        if context.scene is None:
            return {'CANCELLED'}
        
        armature_obj = get_armature_obj(context)
        if armature_obj is None:
            return {'CANCELLED'}

        try:
            c = 0
            for obj in armature_obj.children_recursive:
                if obj.type != "MESH":
                    continue
                c += self.remove_unused_material_slots(obj)
            self.report({'INFO'}, f"Removed {c} unused material slots.")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to remove unused material slots: {e}")
            return {'CANCELLED'}

    def remove_unused_material_slots(self, obj: bpy.types.Object) -> int:
        if obj.type != "MESH":
            return 0

        assert isinstance(obj.data, bpy.types.Mesh)

        removed = 0
        for idx, _ in sorted(_list_unused_material_slots(obj), reverse=True):
            if idx < 0 or idx >= len(obj.data.materials):
                continue
            obj.data.materials.pop(index=idx)
            removed += 1

        self.report({'INFO'}, f"Removed {removed} unused material slots from '{obj.name}'.")
        return removed

@registerme
class VRCACTK_OT_RemoveUnusedAttributesOperator(bpy.types.Operator):
    bl_idname = "vrcactk.remove_unused_attributes_operator"
    bl_label = "Remove Unused Attributes"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def register_me(cls):
        bpy.utils.register_class(cls)

    @classmethod
    def unregister_me(cls):
        bpy.utils.unregister_class(cls)

    def execute(self, context):
        if context is None:
            return {'CANCELLED'}
        if context.scene is None:
            return {'CANCELLED'}
        
        armature = get_armature_obj(context)
        if armature is None:
            return {'CANCELLED'}

        try:
            c = 0
            for obj in armature.children_recursive:
                if obj.type != "MESH":
                    continue
                c += self.remove_unused_attributes(obj)
            self.report({'INFO'}, f"Removed {c} unused attributes.")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to remove unused attributes: {e}")
            return {'CANCELLED'}

    def remove_unused_attributes(self, obj: bpy.types.Object) -> int:
        if obj.type != "MESH":
            return 0
        
        assert isinstance(obj.data, bpy.types.Mesh)

        color_attributes = obj.data.color_attributes
    
        keys_to_remove = []
        for attr in color_attributes:
            if attr.data_type not in {"BYTE_COLOR", "FLOAT_COLOR"}:
                continue

            color_attr = cast(
                bpy.types.ByteColorAttribute | bpy.types.FloatColorAttribute,
                attr,
            )

            if (
                all(
                    value.color[0] == 0
                    and value.color[1] == 0
                    and value.color[2] == 0
                    for value in color_attr.data
                )
                or all(
                    value.color[0] == 1
                    and value.color[1] == 1
                    and value.color[2] == 1
                    for value in color_attr.data
                )
            ):
                keys_to_remove.append(attr.name)

        for key in keys_to_remove:
            color_attributes.remove(color_attributes[key])

        self.report({'INFO'}, f"Removed {len(keys_to_remove)} unused attributes from '{obj.name}'.")
        return len(keys_to_remove)

@registerme
class VRCACTK_OT_ListShapeKeysAffectingSelectionOperator(bpy.types.Operator):
    bl_idname = "vrcactk.list_shape_keys_affecting_selection_operator"
    bl_label = "List Shape Keys Affecting Selection"
    bl_options = {'REGISTER'}

    @classmethod
    def register_me(cls):
        bpy.utils.register_class(cls)

    @classmethod
    def unregister_me(cls):
        bpy.utils.unregister_class(cls)

    def execute(self, context):
        if context is None:
            return {'CANCELLED'}
        obj = context.active_object
        if obj is None or obj.type != "MESH":
            self.report({'ERROR'}, "Active object must be a mesh.")
            return {'CANCELLED'}
        if context.mode != "EDIT_MESH":
            self.report({'ERROR'}, "Must be in Edit Mode on a mesh.")
            return {'CANCELLED'}

        assert isinstance(obj.data, bpy.types.Mesh)

        if not obj.data.shape_keys:
            self.report({'INFO'}, f"No shape keys on '{obj.name}'.")
            return {'FINISHED'}

        bm = bmesh.from_edit_mesh(obj.data)
        selected_indices = {v.index for v in bm.verts if v.select}
        if not selected_indices:
            for f in bm.faces:
                if not f.select:
                    continue
                for v in f.verts:
                    selected_indices.add(v.index)

        if not selected_indices:
            self.report({'INFO'}, "No selected vertices or faces.")
            return {'CANCELLED'}

        tolerance = 1e-5
        affected = []
        kbs = obj.data.shape_keys.key_blocks

        for kb in kbs:
            if kb == kb.relative_key:
                continue
            rel = kb.relative_key
            for idx in selected_indices:
                if (kb.data[idx].co - rel.data[idx].co).length > tolerance: # type: ignore
                    affected.append(kb.name)
                    break

        if affected:
            names = ", ".join(affected)
            self.report({'INFO'}, f"Affecting shape keys ({len(affected)}): {names}")
        else:
            self.report({'INFO'}, "No shape keys affect the selection.")
        return {'FINISHED'}


@registerme
class VRCACTK_OT_SelectVerticesAffectedByShapeKeyOperator(bpy.types.Operator):
    bl_idname = "vrcactk.select_vertices_affected_by_shape_key_operator"
    bl_label = "Select Vertices Affected By Shape Key"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def register_me(cls):
        bpy.utils.register_class(cls)

    @classmethod
    def unregister_me(cls):
        bpy.utils.unregister_class(cls)

    def execute(self, context):
        if context is None:
            return {'CANCELLED'}
        obj = context.active_object
        if obj is None or obj.type != "MESH":
            self.report({'ERROR'}, "Active object must be a mesh.")
            return {'CANCELLED'}
        assert isinstance(obj.data, bpy.types.Mesh)

        if not obj.data.shape_keys:
            self.report({'INFO'}, f"No shape keys on '{obj.name}'.")
            return {'CANCELLED'}

        kb = obj.active_shape_key
        if kb is None:
            self.report({'ERROR'}, "No active shape key selected.")
            return {'CANCELLED'}

        if kb == kb.relative_key:
            self.report({'INFO'}, f"Shape key '{kb.name}' has no deltas.")
            return {'CANCELLED'}

        nverts = len(obj.data.vertices)
        if nverts == 0:
            self.report({'INFO'}, f"No vertices on '{obj.name}'.")
            return {'CANCELLED'}

        tolerance = 1e-5
        kb_locs = np.empty(3 * nverts, dtype=np.float32)
        rel_locs = np.empty(3 * nverts, dtype=np.float32)
        kb.data.foreach_get("co", kb_locs)  # type: ignore
        kb.relative_key.data.foreach_get("co", rel_locs)  # type: ignore

        deltas = kb_locs - rel_locs
        deltas = deltas.reshape((nverts, 3))
        changed = (deltas * deltas).sum(axis=1) > (tolerance * tolerance)

        if context.mode != "EDIT_MESH":
            bpy.ops.object.mode_set(mode="EDIT")

        bpy.ops.mesh.select_mode(type="VERT")
        bpy.ops.mesh.select_all(action='DESELECT')

        bm = bmesh.from_edit_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        for v in bm.verts:
            v.select = bool(changed[v.index])

        bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)

        _view3d_view_selected(context)

        selected_count = int(changed.sum())
        self.report(
            {'INFO'},
            f"Selected {selected_count} vertices affected by '{kb.name}'.",
        )
        return {'FINISHED'}

def _view3d_view_selected(context: bpy.types.Context) -> bool:
    wm = context.window_manager
    if wm is None:
        return False

    for window in wm.windows:
        screen = window.screen
        if screen is None:
            continue
        for area in screen.areas:
            if area.type != "VIEW_3D":
                continue
            region = next(
                (r for r in area.regions if r.type == "WINDOW"),
                None,
            )
            if region is None:
                continue
            with context.temp_override(
                window=window,
                screen=screen,
                area=area,
                region=region,
            ):
                bpy.ops.view3d.view_selected()
            return True
    return False


def _focus_properties_context(context: bpy.types.Context, *, panel: str) -> bool:
    wm = context.window_manager
    if wm is None:
        return False

    for window in wm.windows:
        screen = window.screen
        if screen is None:
            continue
        for area in screen.areas:
            if area.type != "PROPERTIES":
                continue
            region = next((r for r in area.regions if r.type == "WINDOW"), None)
            if region is None:
                continue
            with context.temp_override(
                window=window,
                screen=screen,
                area=area,
                region=region,
            ):
                try:
                    area.spaces.active.context = panel
                except Exception:
                    return False
                return True
    return False


def _activate_object(context: bpy.types.Context, obj: bpy.types.Object) -> bool:
    view_layer = context.view_layer
    if view_layer is None:
        return False

    if context.mode != "OBJECT":
        current_active = view_layer.objects.active
        if current_active is None:
            return False
        try:
            _mode_set(context, current_active, "OBJECT")
        except Exception:
            return False

    collection_paths = _find_layer_collection_paths(
        view_layer.layer_collection,
        set(obj.users_collection),
    )
    if not collection_paths:
        return False
    for collection_path in collection_paths:
        for layer_collection in collection_path:
            layer_collection.exclude = False
            layer_collection.hide_viewport = False
            layer_collection.collection.hide_viewport = False
            layer_collection.collection.hide_select = False

    obj.hide_viewport = False
    obj.hide_select = False
    view_layer.update()
    if obj.name not in view_layer.objects:
        return False

    obj.hide_set(False)
    for other in view_layer.objects:
        if other.select_get():
            other.select_set(False)
    obj.select_set(True)
    view_layer.objects.active = obj
    return view_layer.objects.active == obj and obj.select_get()


def _find_layer_collection_paths(
    layer_collection: bpy.types.LayerCollection,
    target_collections: set[bpy.types.Collection],
    path: list[bpy.types.LayerCollection] | None = None,
) -> list[list[bpy.types.LayerCollection]]:
    current_path = [*(path or []), layer_collection]
    paths: list[list[bpy.types.LayerCollection]] = []
    if layer_collection.collection in target_collections:
        paths.append(current_path)
    for child in layer_collection.children:
        paths.extend(
            _find_layer_collection_paths(
                child,
                target_collections,
                current_path,
            )
        )
    return paths


def _isolate_object_for_geometry(
    context: bpy.types.Context,
    obj: bpy.types.Object,
) -> bool:
    if context.mode != "OBJECT":
        return False

    view_layer = context.view_layer
    if view_layer is None:
        return False

    view_override = _find_view3d_override(context)
    if view_override is not None:
        area = view_override["area"]
        if area.spaces.active.local_view is not None:
            with context.temp_override(**view_override):
                bpy.ops.view3d.localview(frame_selected=False)

    collection_paths = _find_layer_collection_paths(
        view_layer.layer_collection,
        set(obj.users_collection),
    )
    if not collection_paths:
        return False

    for collection_path in collection_paths:
        for layer_collection in collection_path:
            layer_collection.exclude = False
            layer_collection.hide_viewport = False
            layer_collection.collection.hide_viewport = False
            layer_collection.collection.hide_select = False

    obj.hide_viewport = False
    obj.hide_select = False
    view_layer.update()

    for other in list(view_layer.objects):
        other.select_set(False)
        other.hide_set(other != obj)

    obj.hide_set(False)
    obj.select_set(True)
    view_layer.objects.active = obj
    return obj.visible_get(view_layer=view_layer)


def _find_view3d_override(
    context: bpy.types.Context,
    obj: bpy.types.Object | None = None,
) -> dict[str, object] | None:
    wm = context.window_manager
    if wm is None:
        return None

    for window in wm.windows:
        screen = window.screen
        if screen is None:
            continue
        for area in screen.areas:
            if area.type != "VIEW_3D":
                continue
            region = next((r for r in area.regions if r.type == "WINDOW"), None)
            if region is None:
                continue
            override: dict[str, object] = {
                "window": window,
                "screen": screen,
                "area": area,
                "region": region,
            }
            if obj is not None:
                override["active_object"] = obj
                override["object"] = obj
                override["selected_objects"] = [obj]
                override["selected_editable_objects"] = [obj]
            return override
    return None


def _mode_set(context: bpy.types.Context, obj: bpy.types.Object, mode: str) -> None:
    override = _find_view3d_override(context, obj)
    if override is not None:
        with context.temp_override(**override):
            bpy.ops.object.mode_set(mode=mode)
    else:
        bpy.ops.object.mode_set(mode=mode)


def _mesh_select_all(
    context: bpy.types.Context,
    obj: bpy.types.Object,
    *,
    action: str,
) -> None:
    override = _find_view3d_override(context, obj)
    if override is not None:
        with context.temp_override(**override):
            bpy.ops.mesh.select_all(action=action)
    else:
        bpy.ops.mesh.select_all(action=action)


def _mesh_select_mode(
    context: bpy.types.Context,
    obj: bpy.types.Object,
    *,
    mode: str,
) -> None:
    override = _find_view3d_override(context, obj)
    if override is not None:
        with context.temp_override(**override):
            bpy.ops.mesh.select_mode(type=mode)
    else:
        bpy.ops.mesh.select_mode(type=mode)


def _mesh_select_loose(context: bpy.types.Context, obj: bpy.types.Object) -> None:
    if obj.type != "MESH" or context.mode != "EDIT_MESH":
        return

    assert isinstance(obj.data, bpy.types.Mesh)

    # bpy.ops.mesh.select_loose() changes what it considers loose based on the
    # current vertex/edge/face selection mode.  The report, however, always
    # means isolated vertices and edges with no linked faces.  Select those
    # exact elements so that "Show Issue" cannot highlight valid faces when
    # the user happened to be in Face Select mode previously.
    context.tool_settings.mesh_select_mode = (True, True, False)
    bm = bmesh.from_edit_mesh(obj.data)
    for face in bm.faces:
        face.select_set(False)
    for edge in bm.edges:
        edge.select_set(False)
    for vert in bm.verts:
        vert.select_set(False)
    for edge in bm.edges:
        if not edge.link_faces:
            edge.select_set(True)
    for vert in bm.verts:
        if not vert.link_edges:
            vert.select_set(True)
    bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)


def _select_degenerate_geometry(
    context: bpy.types.Context,
    obj: bpy.types.Object,
    *,
    edge_tol: float = 1e-6,
    face_area_tol: float = 1e-12,
    kind: str = "BOTH",
) -> None:
    if context.mode != "EDIT_MESH":
        bpy.ops.object.mode_set(mode="EDIT")
    bm = bmesh.from_edit_mesh(obj.data)
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    edges, faces = _degenerate_geometry_elements(
        bm, edge_tol=edge_tol, face_area_tol=face_area_tol
    )
    if kind in {"EDGES", "BOTH"}:
        selected_edges = set(edges)
        for edge in bm.edges:
            edge.select = edge in selected_edges
    if kind in {"FACES", "BOTH"}:
        for face in faces:
            face.select = True
    bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)


def _select_mesh_element_indices(
    context: bpy.types.Context,
    obj: bpy.types.Object,
    *,
    element_type: str,
    indices: list[int],
) -> None:
    if context.mode != "EDIT_MESH":
        _mode_set(context, obj, "EDIT")
    _mesh_select_mode(context, obj, mode=element_type)
    _mesh_select_all(context, obj, action="DESELECT")

    bm = bmesh.from_edit_mesh(obj.data)
    elements = bm.faces if element_type == "FACE" else bm.verts
    elements.ensure_lookup_table()
    for index in indices:
        if 0 <= index < len(elements):
            elements[index].select = True
    bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
    _view3d_view_selected(context)


def _draw_shape_key_context_menu(self, context: bpy.types.Context) -> None:
    obj = context.active_object
    if obj is None or obj.type != "MESH":
        return
    if not obj.data.shape_keys:
        return
    if obj.active_shape_key is None:
        return

    layout = self.layout
    layout.separator()
    layout.operator(
        "vrcactk.select_vertices_affected_by_shape_key_operator",
        text="Select Affected Vertices",
        icon="VERTEXSEL",
    )


def _draw_mesh_select_context_menu(self, context: bpy.types.Context) -> None:
    if context.mode != "EDIT_MESH":
        return
    obj = context.active_object
    if obj is None or obj.type != "MESH":
        return
    if not obj.data.shape_keys:
        return

    layout = self.layout
    layout.separator()
    layout.operator(
        "vrcactk.list_shape_keys_affecting_selection_operator",
        text="Affected Shape Keys",
        icon="SHAPEKEY_DATA"
    )


@registerme
class VRCACTK_ShapeKeysPanelHook:
    @classmethod
    def register_me(cls):
        bpy.types.MESH_MT_shape_key_context_menu.append(_draw_shape_key_context_menu)
        tree_menu = getattr(bpy.types, "MESH_MT_shape_key_tree_context_menu", None)
        if tree_menu is not None:
            tree_menu.append(_draw_shape_key_context_menu)

    @classmethod
    def unregister_me(cls):
        bpy.types.MESH_MT_shape_key_context_menu.remove(_draw_shape_key_context_menu)
        tree_menu = getattr(bpy.types, "MESH_MT_shape_key_tree_context_menu", None)
        if tree_menu is not None:
            tree_menu.remove(_draw_shape_key_context_menu)


@registerme
class VRCACTK_MeshSelectContextMenuHook:
    @classmethod
    def register_me(cls):
        bpy.types.VIEW3D_MT_edit_mesh_context_menu.append(_draw_mesh_select_context_menu)

    @classmethod
    def unregister_me(cls):
        bpy.types.VIEW3D_MT_edit_mesh_context_menu.remove(_draw_mesh_select_context_menu)


@registerme
class VRCACTK_OT_ReportIssuesOperator(bpy.types.Operator):
    bl_idname = "vrcactk.report_issues_operator"
    bl_label = "Avatar Report"
    bl_options = {'REGISTER'}

    @classmethod
    def register_me(cls):
        bpy.utils.register_class(cls)

    @classmethod
    def unregister_me(cls):
        bpy.utils.unregister_class(cls)

    def execute(self, context):
        return {'FINISHED'}
    
    def draw(self, context):
        layout = self.layout
        analyze_row = layout.row(align=True)
        armature_data = _get_armature_data(context)
        if armature_data is not None:
            analyze_row.prop(
                armature_data,
                "report_refresh",
                text="Analyze Issues",
                toggle=True,
                icon="VIEWZOOM",
            )
        else:
            analyze_row.label(text="Analyze Issues")
        layout.separator()

        if armature_data is None:
            layout.label(text="No armature selected.")
            return

        unresolved_items = [
            (index, issue)
            for index, issue in enumerate(armature_data.report_issues)
            if _find_matching_decision(armature_data, issue) is None
        ]
        active_decisions = sum(
            1 for decision in armature_data.report_decisions if decision.is_active
        )

        if not armature_data.report_has_analysis:
            layout.label(text="Click Analyze Issues to generate a report.")
        elif not unresolved_items:
            if active_decisions:
                layout.label(
                    text=f"No findings need review. {active_decisions} accepted."
                )
            else:
                layout.label(text="No issues found.")
        else:
            layout.label(text=f"Needs Review ({len(unresolved_items)})")
            issues_by_category: dict[
                str,
                list[tuple[int, bpy.types.PropertyGroup]],
            ] = {}
            for issue_index, issue in unresolved_items:
                issues_by_category.setdefault(issue.category, []).append(
                    (issue_index, issue)
                )

            for category, issues in issues_by_category.items():
                expand_prop = {
                    "Degenerate Geometry": "report_expand_degenerate_geometry",
                    "Loose Geometry": "report_expand_loose_geometry",
                    "Unweighted Vertices": "report_expand_unweighted_vertices",
                    "Unused Shape Keys": "report_expand_unused_shape_keys",
                    "Unused Vertex Groups": "report_expand_unused_vertex_groups",
                    "Unused Material Slots": "report_expand_unused_material_slots",
                    "Multiple UV Maps": "report_expand_multiple_uv_maps",
                    "Unused Bones": "report_expand_unused_bones",
                    "Unconnected Bone Chains": "report_expand_unconnected_bone_chains",
                    "Unapplied Transforms": "report_expand_unapplied_transforms",
                    "Shape Key Basis Mismatch": "report_expand_shape_key_basis_mismatch",
                }.get(category)
                category_descriptions = {
                    "Degenerate Geometry": "Zero-length edges (length <= 1e-6) or zero-area faces (area <= 1e-12), in mesh-local units. Geometry moved by shape keys is excluded.",
                    "Loose Geometry": "Vertices/edges not connected to any face.",
                    "Unweighted Vertices": "Vertices without a positive weight for any bone in the avatar armature.",
                    "Unused Shape Keys": "Shape keys with no deformation compared to their basis. Decoratively named separator keys are excluded using a heuristic.",
                    "Unused Vertex Groups": "Vertex groups with no weighted vertices or not associated with a bone.",
                    "Unused Material Slots": "Material slots that are not used by any faces.",
                    "Multiple UV Maps": "Extra UV maps may be intentional or used by Unity materials and scripts.",
                    "Unused Bones": "Armature bones not referenced by any vertex weights.",
                    "Unconnected Bone Chains": "Parent tails that do not meet any immediate child head; Unity displays these relationships as connected.",
                    "Unapplied Transforms": "Objects with non-zero location/rotation or non-1 scale.",
                    "Shape Key Basis Mismatch": "Shape keys without a proper Basis in slot 0.",
                }
                expand_value = True
                if expand_prop:
                    expand_value = bool(getattr(armature_data, expand_prop))

                header_box = layout.box()
                header_row = header_box.row(align=True)
                header_row.alignment = "LEFT"
                header_text = f"{category} ({len(issues)})"
                if expand_prop:
                    icon = "TRIA_DOWN" if expand_value else "TRIA_RIGHT"
                    header_row.prop(
                        armature_data,
                        expand_prop,
                        text=header_text,
                        icon=icon,
                        emboss=False,
                    )
                else:
                    header_row.label(text=header_text)

                if not expand_value:
                    continue

                description_text = category_descriptions.get(category)
                if description_text:
                    header_box.label(text=description_text)

                for issue_index, issue in issues:
                    box = header_box.box()
                    description_lines = issue.description.splitlines() or [""]
                    box.label(text=description_lines[0])

                    for description_line in description_lines[1:]:
                        box.label(text=description_line)

                    shows_evidence_list = not (
                        issue.issue_type == "UNCONNECTED_BONE_CHAIN"
                        and not issue.has_auto_fix
                    )
                    if shows_evidence_list and len(issue.evidence) > 1:
                        evidence_col = box.column(align=True)
                        for evidence in issue.evidence:
                            evidence_col.label(text=evidence.label, icon="DOT")

                    box.separator(factor=0.5)
                    actions = box.column(align=False)

                    reanalyze_row = actions.row()
                    reanalyze_row.enabled = context.mode == "OBJECT"
                    reanalyze_op = reanalyze_row.operator(
                        VRCACTK_OT_ReanalyzeReportIssueOperator.bl_idname,
                        text="Reanalyze",
                        icon="FILE_REFRESH",
                    )
                    reanalyze_op.issue_index = issue_index
                    actions.separator(factor=0.35)

                    if issue.issue_type == "DEGENERATE_GEOMETRY":
                        edges_row = actions.row()
                        edges_row.enabled = context.mode == "OBJECT"
                        edges_op = edges_row.operator(
                            VRCACTK_OT_ShowReportIssueOperator.bl_idname,
                            text="Show Edges",
                            icon="EDGESEL",
                        )
                        edges_op.issue_type = issue.issue_type
                        edges_op.object_name = issue.object_name
                        edges_op.item_name = issue.item_name
                        edges_op.slot_index = issue.slot_index
                        edges_op.show_kind = "EDGES"
                        actions.separator(factor=0.35)
                        faces_row = actions.row()
                        faces_row.enabled = context.mode == "OBJECT"
                        faces_op = faces_row.operator(
                            VRCACTK_OT_ShowReportIssueOperator.bl_idname,
                            text="Show Faces",
                            icon="FACESEL",
                        )
                        faces_op.issue_type = issue.issue_type
                        faces_op.object_name = issue.object_name
                        faces_op.item_name = issue.item_name
                        faces_op.slot_index = issue.slot_index
                        faces_op.show_kind = "FACES"
                    else:
                        show_row = actions.row()
                        if issue.issue_type in _GEOMETRY_REPORT_ISSUE_TYPES:
                            show_row.enabled = context.mode == "OBJECT"
                        show_op = show_row.operator(
                            VRCACTK_OT_ShowReportIssueOperator.bl_idname,
                            text="Show",
                            icon="VIEWZOOM",
                        )
                        show_op.issue_type = issue.issue_type
                        show_op.object_name = issue.object_name
                        show_op.item_name = issue.item_name
                        show_op.slot_index = issue.slot_index

                    if issue.has_auto_fix:
                        actions.separator(factor=0.35)
                        auto_fix_row = actions.row()
                        auto_fix_row.enabled = context.mode == "OBJECT"
                        auto_fix_op = auto_fix_row.operator(
                            VRCACTK_OT_AutoFixReportIssueOperator.bl_idname,
                            text="Auto Fix",
                            icon="MODIFIER",
                        )
                        auto_fix_op.issue_index = issue_index

                    if (
                        issue.issue_type == "UNCONNECTED_BONE_CHAIN"
                        and not issue.has_auto_fix
                    ):
                        actions.separator(factor=0.35)
                        align_col = actions.column(align=True)
                        align_col.enabled = context.mode == "OBJECT"
                        align_col.label(text="Align tail to child:")
                        for evidence in issue.evidence:
                            align_op = align_col.operator(
                                VRCACTK_OT_AlignBoneToChildReportIssueOperator.bl_idname,
                                text=evidence.label,
                                icon="BONE_DATA",
                            )
                            align_op.object_name = issue.object_name
                            align_op.parent_name = issue.item_name
                            align_op.child_name = evidence.key

                    if issue.can_accept:
                        actions.separator(factor=0.35)
                        accept_op = actions.operator(
                            VRCACTK_OT_AcceptReportIssueOperator.bl_idname,
                            text="Accept as Intentional",
                            icon="CHECKMARK",
                        )
                        accept_op.issue_index = issue_index

        if armature_data.report_decisions:
            layout.separator()
            accepted_box = layout.box()
            accepted_row = accepted_box.row(align=True)
            accepted_expanded = armature_data.report_expand_accepted_decisions
            accepted_row.prop(
                armature_data,
                "report_expand_accepted_decisions",
                text=f"Accepted Decisions ({len(armature_data.report_decisions)})",
                icon="TRIA_DOWN" if accepted_expanded else "TRIA_RIGHT",
                emboss=False,
            )
            if accepted_expanded:
                for decision_index, decision in enumerate(
                    armature_data.report_decisions
                ):
                    decision_box = accepted_box.box()
                    description_lines = decision.description.splitlines() or [""]
                    status_row = decision_box.row(align=True)
                    status_row.label(
                        text=description_lines[0],
                        icon="CHECKMARK" if decision.is_active else "INFO",
                    )
                    reconsider_op = status_row.operator(
                        VRCACTK_OT_ReconsiderReportDecisionOperator.bl_idname,
                        text="Reconsider",
                        icon="LOOP_BACK",
                    )
                    reconsider_op.decision_index = decision_index
                    for description_line in description_lines[1:]:
                        decision_box.label(text=description_line)
                    state_text = (
                        "Currently accepted"
                        if decision.is_active
                        else "No longer matches the current analysis"
                    )
                    decision_box.label(text=state_text)
                    for item in decision.accepted_items:
                        decision_box.label(text=item.label, icon="DOT")
                    if decision.note:
                        decision_box.label(text=decision.note, icon="GREASEPENCIL")

    def invoke(self, context, event):
        wm = context.window_manager
        if wm is None:
            return {'CANCELLED'}
        return wm.invoke_props_dialog(self, width=700)


@registerme
class VRCACTK_OT_ReanalyzeReportIssueOperator(bpy.types.Operator):
    bl_idname = "vrcactk.reanalyze_report_issue_operator"
    bl_label = "Reanalyze Finding"
    bl_options = {'REGISTER'}

    issue_index: bpy.props.IntProperty(default=-1)

    @classmethod
    def register_me(cls):
        bpy.utils.register_class(cls)

    @classmethod
    def unregister_me(cls):
        bpy.utils.unregister_class(cls)

    def execute(self, context):
        if context is None or context.scene is None:
            return {'CANCELLED'}
        if context.mode != "OBJECT":
            self.report(
                {'ERROR'},
                "Report findings can only be reanalyzed from Object Mode.",
            )
            return {'CANCELLED'}

        armature_data = _get_armature_data(context)
        if armature_data is None:
            return {'CANCELLED'}
        if self.issue_index < 0 or self.issue_index >= len(armature_data.report_issues):
            self.report({'ERROR'}, "The report finding no longer exists.")
            return {'CANCELLED'}

        issue = armature_data.report_issues[self.issue_index]
        issue_type = issue.issue_type
        target_object = issue.target_object
        if target_object is None:
            self.report({'ERROR'}, "The affected object no longer exists.")
            return {'CANCELLED'}

        if not _populate_report_issues(
            context,
            issue_types={issue_type},
            target_objects={target_object},
        ):
            self.report({'ERROR'}, "Failed to reanalyze the finding.")
            return {'CANCELLED'}

        still_detected = any(
            current.issue_type == issue_type
            and current.target_object == target_object
            for current in armature_data.report_issues
        )
        self.report(
            {'INFO'},
            "Finding is still present."
            if still_detected
            else "Finding is no longer detected.",
        )
        return {'FINISHED'}


@registerme
class VRCACTK_OT_AcceptReportIssueOperator(bpy.types.Operator):
    bl_idname = "vrcactk.accept_report_issue_operator"
    bl_label = "Accept Finding as Intentional"
    bl_options = {'REGISTER', 'UNDO'}

    issue_index: bpy.props.IntProperty(default=-1)

    @classmethod
    def register_me(cls):
        bpy.utils.register_class(cls)

    @classmethod
    def unregister_me(cls):
        bpy.utils.unregister_class(cls)

    def execute(self, context):
        armature_data = _get_armature_data(context)
        if armature_data is None:
            return {'CANCELLED'}
        if self.issue_index < 0 or self.issue_index >= len(armature_data.report_issues):
            self.report({'ERROR'}, "The report finding no longer exists.")
            return {'CANCELLED'}

        issue = armature_data.report_issues[self.issue_index]
        if (
            not issue.can_accept
            or issue.issue_type in _NON_ACCEPTABLE_REPORT_ISSUE_TYPES
        ):
            self.report(
                {'ERROR'},
                "This finding cannot be accepted as intentional.",
            )
            return {'CANCELLED'}
        if _find_matching_decision(armature_data, issue) is not None:
            return {'FINISHED'}
        issue.do_fix = False

        decision = armature_data.report_decisions.add()
        decision.issue_type = issue.issue_type
        decision.category = issue.category
        decision.description = issue.description
        decision.target_object = issue.target_object
        decision.object_name = issue.object_name
        decision.item_name = issue.item_name
        decision.slot_index = issue.slot_index
        decision.is_active = True
        for evidence in issue.evidence:
            accepted_item = decision.accepted_items.add()
            accepted_item.key = evidence.key
            accepted_item.label = evidence.label

        self.report({'INFO'}, "Finding accepted as intentional.")
        return {'FINISHED'}


@registerme
class VRCACTK_OT_ReconsiderReportDecisionOperator(bpy.types.Operator):
    bl_idname = "vrcactk.reconsider_report_decision_operator"
    bl_label = "Reconsider Accepted Decision"
    bl_options = {'REGISTER', 'UNDO'}

    decision_index: bpy.props.IntProperty(default=-1)

    @classmethod
    def register_me(cls):
        bpy.utils.register_class(cls)

    @classmethod
    def unregister_me(cls):
        bpy.utils.unregister_class(cls)

    def execute(self, context):
        armature_data = _get_armature_data(context)
        if armature_data is None:
            return {'CANCELLED'}
        if (
            self.decision_index < 0
            or self.decision_index >= len(armature_data.report_decisions)
        ):
            self.report({'ERROR'}, "The accepted decision no longer exists.")
            return {'CANCELLED'}

        armature_data.report_decisions.remove(self.decision_index)
        self.report({'INFO'}, "Finding returned to the review queue.")
        return {'FINISHED'}


@registerme
class VRCACTK_OT_AutoFixReportIssueOperator(bpy.types.Operator):
    bl_idname = "vrcactk.auto_fix_report_issue_operator"
    bl_label = "Auto Fix Finding"
    bl_options = {'REGISTER', 'UNDO'}

    issue_index: bpy.props.IntProperty(default=-1)

    @classmethod
    def register_me(cls):
        bpy.utils.register_class(cls)

    @classmethod
    def unregister_me(cls):
        bpy.utils.unregister_class(cls)

    def execute(self, context):
        if context is None or context.scene is None:
            return {'CANCELLED'}
        if context.mode != "OBJECT":
            self.report(
                {'ERROR'},
                "Report findings can only be fixed from Object Mode.",
            )
            return {'CANCELLED'}

        armature_data = _get_armature_data(context)
        if armature_data is None:
            return {'CANCELLED'}
        if self.issue_index < 0 or self.issue_index >= len(armature_data.report_issues):
            self.report({'ERROR'}, "The report finding no longer exists.")
            return {'CANCELLED'}

        issue = armature_data.report_issues[self.issue_index]
        if not issue.has_auto_fix:
            self.report({'ERROR'}, "This finding does not have an auto fix.")
            return {'CANCELLED'}

        issue_type = issue.issue_type
        target_object = issue.target_object
        if target_object is None:
            self.report({'ERROR'}, "The affected object no longer exists.")
            return {'CANCELLED'}

        for current in armature_data.report_issues:
            current.do_fix = False
        issue.do_fix = True

        if not _apply_selected_fixes(context):
            self.report({'ERROR'}, "Failed to apply the fix.")
            return {'CANCELLED'}

        if not _populate_report_issues(
            context,
            issue_types={issue_type},
            target_objects={target_object},
        ):
            self.report({'ERROR'}, "The fix was applied, but reanalysis failed.")
            return {'CANCELLED'}

        self.report({'INFO'}, "Auto fix applied and finding reanalyzed.")
        return {'FINISHED'}


@registerme
class VRCACTK_OT_AlignBoneToChildReportIssueOperator(bpy.types.Operator):
    bl_idname = "vrcactk.align_bone_to_child_report_issue_operator"
    bl_label = "Align Bone Tail to Child"
    bl_options = {'REGISTER', 'UNDO'}

    object_name: bpy.props.StringProperty(name="Armature", default="")
    parent_name: bpy.props.StringProperty(name="Parent Bone", default="")
    child_name: bpy.props.StringProperty(name="Child Bone", default="")

    @classmethod
    def register_me(cls):
        bpy.utils.register_class(cls)

    @classmethod
    def unregister_me(cls):
        bpy.utils.unregister_class(cls)

    def execute(self, context):
        if context is None or context.scene is None:
            return {'CANCELLED'}
        if context.mode != "OBJECT":
            self.report(
                {'ERROR'},
                "Bone tails can only be aligned from Object Mode.",
            )
            return {'CANCELLED'}

        obj = context.scene.objects.get(self.object_name)
        if obj is None or obj.type != "ARMATURE":
            self.report({'ERROR'}, "The affected armature no longer exists.")
            return {'CANCELLED'}

        parent = obj.data.bones.get(self.parent_name)
        child = obj.data.bones.get(self.child_name)
        if parent is None or child is None or child.parent != parent:
            self.report(
                {'ERROR'},
                "The selected bones are no longer an immediate parent-child pair.",
            )
            return {'CANCELLED'}

        _align_bone_tails(
            context,
            obj,
            {self.parent_name: self.child_name},
        )
        if not _populate_report_issues(
            context,
            issue_types={"UNCONNECTED_BONE_CHAIN"},
            target_objects={obj},
        ):
            self.report({'ERROR'}, "The alignment was applied, but reanalysis failed.")
            return {'CANCELLED'}

        self.report(
            {'INFO'},
            f"Aligned '{self.parent_name}' to '{self.child_name}'.",
        )
        return {'FINISHED'}


@registerme
class VRCACTK_OT_ShowReportIssueOperator(bpy.types.Operator):
    bl_idname = "vrcactk.show_report_issue_operator"
    bl_label = "Show Issue"
    bl_options = {'REGISTER'}

    issue_type: bpy.props.StringProperty(name="Issue Type", default="")
    object_name: bpy.props.StringProperty(name="Object Name", default="")
    item_name: bpy.props.StringProperty(name="Item Name", default="")
    slot_index: bpy.props.IntProperty(name="Slot Index", default=-1)
    show_kind: bpy.props.StringProperty(name="Show Kind", default="")

    @classmethod
    def register_me(cls):
        bpy.utils.register_class(cls)

    @classmethod
    def unregister_me(cls):
        bpy.utils.unregister_class(cls)

    def execute(self, context):
        if context is None or context.scene is None:
            return {'CANCELLED'}

        shows_geometry = self.issue_type in _GEOMETRY_REPORT_ISSUE_TYPES
        if shows_geometry and context.mode != "OBJECT":
            self.report(
                {'ERROR'},
                "Geometry findings can only be shown from Object Mode.",
            )
            return {'CANCELLED'}

        obj = context.scene.objects.get(self.object_name)
        if obj is None:
            self.report({'ERROR'}, "Object not found.")
            return {'CANCELLED'}

        if shows_geometry:
            if not _isolate_object_for_geometry(context, obj):
                self.report(
                    {'ERROR'},
                    "Could not make the affected object visible in this view layer.",
                )
                return {'CANCELLED'}
        elif not _activate_object(context, obj):
            self.report({'ERROR'}, "Could not activate the affected object.")
            return {'CANCELLED'}

        if self.issue_type == "LOOSE_GEOMETRY":
            if obj.type != "MESH":
                self.report({'ERROR'}, "Mesh not found.")
                return {'CANCELLED'}
            if context.mode != "EDIT_MESH":
                _mode_set(context, obj, "EDIT")
            _mesh_select_all(context, obj, action="DESELECT")
            _mesh_select_loose(context, obj)
            return {'FINISHED'}

        if self.issue_type == "DEGENERATE_GEOMETRY":
            if obj.type != "MESH":
                self.report({'ERROR'}, "Mesh not found.")
                return {'CANCELLED'}
            if context.mode != "EDIT_MESH":
                _mode_set(context, obj, "EDIT")
            if self.show_kind == "FACES":
                _mesh_select_mode(context, obj, mode="FACE")
            else:
                _mesh_select_mode(context, obj, mode="EDGE")
            _mesh_select_all(context, obj, action="DESELECT")
            _select_degenerate_geometry(
                context,
                obj,
                kind=self.show_kind or "BOTH",
            )
            return {'FINISHED'}

        if self.issue_type == "UNWEIGHTED_VERTICES":
            if obj.type != "MESH":
                self.report({'ERROR'}, "Mesh not found.")
                return {'CANCELLED'}
            armature_obj = get_armature_obj(context)
            if armature_obj is None:
                self.report({'ERROR'}, "Avatar armature not found.")
                return {'CANCELLED'}
            vertex_indices = _find_unweighted_vertices(obj, armature_obj)
            _select_mesh_element_indices(
                context,
                obj,
                element_type="VERT",
                indices=vertex_indices,
            )
            return {'FINISHED'}

        if self.issue_type == "UNUSED_SHAPE_KEY":
            if obj.type != "MESH":
                self.report({'ERROR'}, "Mesh not found.")
                return {'CANCELLED'}
            if context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            if obj.data.shape_keys:
                for idx, kb in enumerate(obj.data.shape_keys.key_blocks):
                    if kb.name == self.item_name:
                        obj.active_shape_key_index = idx
                        break
            _focus_properties_context(context, panel="DATA")
            return {'FINISHED'}

        if self.issue_type == "UNUSED_MATERIAL_SLOT":
            if obj.type != "MESH":
                self.report({'ERROR'}, "Mesh not found.")
                return {'CANCELLED'}
            if context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            if self.slot_index >= 0:
                obj.active_material_index = self.slot_index
            _focus_properties_context(context, panel="MATERIAL")
            return {'FINISHED'}

        if self.issue_type == "MULTIPLE_UV_MAPS":
            if obj.type != "MESH":
                self.report({'ERROR'}, "Mesh not found.")
                return {'CANCELLED'}
            if context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            if obj.data.uv_layers:
                for idx, uv in enumerate(obj.data.uv_layers):
                    if uv.name == self.item_name:
                        obj.data.uv_layers.active_index = idx
                        break
            _focus_properties_context(context, panel="DATA")
            return {'FINISHED'}

        if self.issue_type in {"UNUSED_BONE", "UNCONNECTED_BONE_CHAIN"}:
            if obj.type != "ARMATURE":
                self.report({'ERROR'}, "Armature not found.")
                return {'CANCELLED'}
            if context.mode != "EDIT_ARMATURE":
                _mode_set(context, obj, "EDIT")
            for bone in obj.data.edit_bones:
                bone.select = False
            edit_bone = obj.data.edit_bones.get(self.item_name)
            if edit_bone is not None:
                edit_bone.select = True
                edit_bone.select_head = True
                edit_bone.select_tail = True
                obj.data.edit_bones.active = edit_bone
            _focus_properties_context(context, panel="DATA")
            return {'FINISHED'}

        if self.issue_type == "UNAPPLIED_TRANSFORMS":
            if context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            _focus_properties_context(context, panel="OBJECT")
            return {'FINISHED'}

        if self.issue_type == "SHAPE_KEY_BASIS_MISMATCH":
            if obj.type != "MESH":
                self.report({'ERROR'}, "Mesh not found.")
                return {'CANCELLED'}
            if context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            if obj.data.shape_keys:
                for idx, kb in enumerate(obj.data.shape_keys.key_blocks):
                    if kb.name == "Basis":
                        obj.active_shape_key_index = idx
                        break
            _focus_properties_context(context, panel="DATA")
            return {'FINISHED'}

        return {'FINISHED'}
