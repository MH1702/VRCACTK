# VRCACTK

**VRChat Avatar Creation Toolkit** — a Blender add-on for inspecting, preparing,
and exporting avatars.

[![Build](https://github.com/MH1702/VRCACTK/actions/workflows/release.yml/badge.svg)](https://github.com/MH1702/VRCACTK/actions/workflows/release.yml)
![Blender](https://img.shields.io/badge/Blender-4.2%2B-orange)
![Status](https://img.shields.io/badge/status-work_in_progress-yellow)
[![License](https://img.shields.io/badge/license-GPL--3.0--or--later-blue)](LICENSE)

[Download](https://github.com/MH1702/VRCACTK/releases/latest) ·
[Report an issue](https://github.com/MH1702/VRCACTK/issues) ·
[Installation](#download-and-install)

> **Work in progress — unfinished and experimental.**
> This toolkit is still being developed. Features, workflows, and the interface
> may change, and bugs or incomplete behavior are expected. I plan to add more
> features over time; the list below describes what is implemented today.
> Keep a backup of your avatar before applying cleanup or fixes.

## What it can do today

### Avatar import and selection

- Import an FBX model from the toolkit panel when the scene has no armature.
- Select an avatar armature from the sidebar to work with its associated meshes.

### Avatar report

Analyze the selected avatar and review findings grouped by category. Current
checks cover:

| Area | Findings |
| --- | --- |
| Mesh geometry | Degenerate geometry, loose geometry, and unweighted vertices |
| Mesh data | Unused vertex groups, unused material slots, and multiple UV maps |
| Shape keys | Unused shape keys and basis mismatches |
| Rigging | Unused bones and unconnected bone chains |
| Transforms | Unapplied transforms |

The report includes controls to locate affected items, reanalyze individual
findings, apply supported automatic fixes, or accept findings as intentional.
Accepted decisions can be reconsidered later. Bone-chain findings also offer
bone-tail alignment controls where applicable.

**Not every finding is an error, and not every finding has an automatic fix.**
The report is a review aid, not a complete VRChat SDK validation pass.

### Shape-key inspection

- List the shape keys affecting selected vertices from the mesh Edit Mode context menu.
- Select vertices affected by the active shape key from its context menu.

### FBX export

- Export the selected avatar armature and its skinned meshes into a single FBX.
- Review a warning if the avatar still has unresolved report findings.
- Prepare temporary copies for export, including transforms and coordinate
  orientation, then clean them up and restore the original names and selection.

## Requirements and current limits

- **Blender 4.2 or newer.** No separate legacy package is provided for Blender 4.1 or older.
- The current import/export workflow uses **FBX**.
- This is a Blender preparation toolkit; uploading an avatar to VRChat remains
  a separate workflow in Unity and the VRChat SDK.
- New Blender versions are allowed, but compatibility with every release and
  every avatar has not been verified.

## Download and install

1. Open [the latest release](https://github.com/MH1702/VRCACTK/releases/latest).
2. Download the `vrcactk-<version>.zip` asset under **Assets**, not GitHub's source-code ZIP.
3. In Blender, open **Edit > Preferences > Get Extensions**.
4. Open the menu in the upper-right corner and choose **Install from Disk**.
5. Select the downloaded ZIP without extracting it, and enable the extension.
6. In the 3D Viewport, press **N** and select the **VRCACTK** tab.

Releases in a private repository are only available to people with repository access.
If you previously installed the legacy VRCBTK/VRCACTK add-on, disable and remove
that copy before installing this extension to avoid duplicate operators.

## Updates and feedback

Install the ZIP from a newer release using the same steps. This GitHub Releases
setup does not provide automatic update discovery inside Blender.

Report bugs and feature requests in [GitHub Issues](https://github.com/MH1702/VRCACTK/issues).
Please include your Blender version, add-on version, steps to reproduce, and any
error messages. A minimal example or screenshot is helpful when possible.

## What's next

I plan to expand the toolkit with more avatar-creation features and improve the
existing tools as development continues. There is no fixed feature list or
release schedule yet. Suggestions and feedback are welcome.

## Building and releasing

Requires Python 3.11+ and Blender 4.2+ (available as `blender` on PATH, or supplied
with `--blender /path/to/blender`).

```sh
python scripts/build_release.py
blender --background --factory-startup --python-exit-code 1 --python scripts/smoke_test.py -- dist/vrcactk-1.0.0.zip
```

The build includes only the extension modules, manifest, README, and license.
The manifest is the source of truth for the version and compatibility metadata.

For a release:

1. Update `version` in `blender_manifest.toml`.
2. Test the package, including import/export with a representative avatar in Blender.
3. Commit and push to `main`; wait for the build workflow to pass.
4. Tag that commit with the matching version and push the tag:

```sh
git tag v1.0.0
git push origin v1.0.0
```

GitHub Actions validates and smoke-tests the package in Blender 4.2.0, then
publishes a GitHub Release with the installable ZIP. Branch and pull-request
builds upload workflow artifacts without publishing releases.

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).
