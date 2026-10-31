import math
import os

import bpy

from .typing_helpers import get_armature_obj
from .util import registerme


def _safe_filename(name: str) -> str:
    for character in '<>:"/\\|?*':
        name = name.replace(character, "_")
    return name.strip() or "Avatar"


def _collect_skinned_meshes(
    scene: bpy.types.Scene,
    armature_obj: bpy.types.Object,
) -> list[bpy.types.Object]:
    return [
        obj
        for obj in scene.objects
        if obj.type == "MESH"
        and any(
            modifier.type == "ARMATURE" and modifier.object == armature_obj
            for modifier in obj.modifiers
        )
    ]


def _unique_temporary_name(name: str, collection) -> str:
    base = f"{name}__vrcactk_original"
    candidate = base
    suffix = 1
    while candidate in collection:
        candidate = f"{base}_{suffix}"
        suffix += 1
    return candidate


def _duplicate_avatar(
    context: bpy.types.Context,
    armature_obj: bpy.types.Object,
    mesh_objects: list[bpy.types.Object],
) -> tuple[bpy.types.Collection, bpy.types.Object, list[bpy.types.Object]]:
    collection = bpy.data.collections.new("VRCACTK_Export")
    context.scene.collection.children.link(collection)

    armature_copy = armature_obj.copy()
    armature_copy.data = armature_obj.data.copy()
    collection.objects.link(armature_copy)

    mesh_copies: list[bpy.types.Object] = []
    for mesh_obj in mesh_objects:
        mesh_copy = mesh_obj.copy()
        mesh_copy.data = mesh_obj.data.copy()
        collection.objects.link(mesh_copy)

        # Put every skinned mesh under the exported armature while retaining its
        # world-space placement. This lets the 90 degree export rotation act on
        # the avatar as a whole, even if the source mesh was not parented.
        world_matrix = mesh_copy.matrix_world.copy()
        mesh_copy.parent = armature_copy
        mesh_copy.parent_type = "OBJECT"
        mesh_copy.matrix_world = world_matrix

        for modifier in mesh_copy.modifiers:
            if modifier.type == "ARMATURE" and modifier.object == armature_obj:
                modifier.object = armature_copy

        mesh_copies.append(mesh_copy)

    return collection, armature_copy, mesh_copies


def _use_source_names(
    armature_obj: bpy.types.Object,
    armature_copy: bpy.types.Object,
    mesh_objects: list[bpy.types.Object],
    mesh_copies: list[bpy.types.Object],
    renamed: list[tuple[bpy.types.ID, str]],
) -> None:

    pairs = [(armature_obj, armature_copy), *zip(mesh_objects, mesh_copies)]
    for source, duplicate in pairs:
        source_name = source.name
        renamed.append((source, source_name))
        source.name = _unique_temporary_name(source_name, bpy.data.objects)
        duplicate.name = source_name

        if source.data is None or duplicate.data is None:
            continue

        data_collection = (
            bpy.data.armatures if source.type == "ARMATURE" else bpy.data.meshes
        )
        data_name = source.data.name
        renamed.append((source.data, data_name))
        source.data.name = _unique_temporary_name(data_name, data_collection)
        duplicate.data.name = data_name

def _restore_names(renamed: list[tuple[bpy.types.ID, str]]) -> None:
    for data_block, original_name in reversed(renamed):
        try:
            data_block.name = original_name
        except ReferenceError:
            pass


def _remove_export_copies(collection: bpy.types.Collection) -> None:
    copied_data = [obj.data for obj in collection.objects if obj.data is not None]
    for obj in list(collection.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    bpy.data.collections.remove(collection)

    for data in copied_data:
        if data.users != 0:
            continue
        if isinstance(data, bpy.types.Mesh):
            bpy.data.meshes.remove(data)
        elif isinstance(data, bpy.types.Armature):
            bpy.data.armatures.remove(data)


def _prepare_for_export(
    context: bpy.types.Context,
    armature_obj: bpy.types.Object,
    mesh_objects: list[bpy.types.Object],
) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    armature_obj.select_set(True)
    for mesh_obj in mesh_objects:
        mesh_obj.select_set(True)
    context.view_layer.objects.active = armature_obj

    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    # Bake Blender's Z-up to Unity's Y-up correction into the exported rig.
    # Only the temporary armature copy is transformed; its child meshes follow
    # the rotation and the source avatar remains untouched.
    for mesh_obj in mesh_objects:
        mesh_obj.select_set(False)
    armature_obj.rotation_euler.rotate_axis("X", math.radians(-90.0))
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)

    # Restore the complete avatar selection for use_selection=True below.
    for mesh_obj in mesh_objects:
        mesh_obj.select_set(True)


@registerme
class VRCACTK_OT_ExportAvatar(bpy.types.Operator):
    bl_idname = "vrcactk.export_avatar"
    bl_label = "Export Avatar"
    bl_options = {"REGISTER"}

    filename_ext = ".fbx"
    filter_glob: bpy.props.StringProperty(default="*.fbx", options={"HIDDEN"})
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    unreviewed_confirmed: bpy.props.BoolProperty(
        default=False,
        options={"HIDDEN", "SKIP_SAVE"},
    )
    unreviewed_count: bpy.props.IntProperty(
        default=0,
        options={"HIDDEN", "SKIP_SAVE"},
    )

    @classmethod
    def register_me(cls):
        bpy.utils.register_class(cls)

    @classmethod
    def unregister_me(cls):
        bpy.utils.unregister_class(cls)

    def execute(self, context):
        if context is None or context.scene is None:
            return {"CANCELLED"}
        if context.mode != "OBJECT":
            self.report({"ERROR"}, "Avatar export must be run in Object Mode.")
            return {"CANCELLED"}

        armature_obj = get_armature_obj(context)
        if armature_obj is None or armature_obj.type != "ARMATURE":
            self.report({"ERROR"}, "No avatar armature is selected.")
            return {"CANCELLED"}

        mesh_objects = _collect_skinned_meshes(context.scene, armature_obj)
        if not mesh_objects:
            self.report({"ERROR"}, "The selected armature has no skinned meshes.")
            return {"CANCELLED"}

        if not self.unreviewed_confirmed:
            from . import util_operations

            if util_operations._populate_report_issues(context):
                unresolved = util_operations._get_unresolved_report_issues(context)
                if unresolved:
                    self.unreviewed_count = len(unresolved)
                    self.unreviewed_confirmed = True
                    return context.window_manager.invoke_props_dialog(
                        self,
                        width=520,
                    )

        filepath = bpy.path.ensure_ext(self.filepath, self.filename_ext)
        output_directory = os.path.dirname(filepath)
        if not filepath or not output_directory or not os.path.isdir(output_directory):
            self.report({"ERROR"}, "Select a valid FBX output path.")
            return {"CANCELLED"}

        view_layer = context.view_layer
        previous_selection = list(context.selected_objects)
        previous_active = view_layer.objects.active
        export_collection = None
        renamed: list[tuple[bpy.types.ID, str]] = []

        try:
            export_collection, armature_copy, mesh_copies = _duplicate_avatar(
                context,
                armature_obj,
                mesh_objects,
            )
            _use_source_names(
                armature_obj,
                armature_copy,
                mesh_objects,
                mesh_copies,
                renamed,
            )
            _prepare_for_export(context, armature_copy, mesh_copies)

            bpy.ops.export_scene.fbx(
                filepath=filepath,
                use_selection=True,
                object_types={"ARMATURE", "MESH"},
                apply_unit_scale=True,
                apply_scale_options="FBX_SCALE_UNITS",
                axis_forward="Z",
                axis_up="Y",
                use_space_transform=True,
                primary_bone_axis="Y",
                secondary_bone_axis="X",
                add_leaf_bones=False,
            )
        except Exception as error:
            self.report({"ERROR"}, f"Avatar export failed: {error}")
            return {"CANCELLED"}
        finally:
            try:
                if export_collection is not None:
                    _remove_export_copies(export_collection)
            finally:
                _restore_names(renamed)

                bpy.ops.object.select_all(action="DESELECT")
                for obj in previous_selection:
                    try:
                        obj.select_set(True)
                    except ReferenceError:
                        pass
                view_layer.objects.active = previous_active

        self.report(
            {"INFO"},
            f"Exported {len(mesh_objects)} skinned meshes to one FBX.",
        )
        return {"FINISHED"}

    def draw(self, context):
        if self.unreviewed_count <= 0:
            return
        layout = self.layout
        layout.label(text="This avatar still has findings that need review.", icon="ERROR")
        layout.label(
            text=f"Outstanding findings: {self.unreviewed_count}"
        )
        layout.label(text="Choose OK to export anyway, or review the report first.")
        layout.operator("vrcactk.report_issues_operator", text="Review Avatar Report")

    def invoke(self, context, event):
        if context is None:
            return {"CANCELLED"}

        self.unreviewed_confirmed = False
        self.unreviewed_count = 0

        armature_obj = get_armature_obj(context)
        if armature_obj is not None and not self.filepath:
            filename = f"{_safe_filename(armature_obj.name)}{self.filename_ext}"
            self.filepath = os.path.join(bpy.path.abspath("//"), filename)

        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}
