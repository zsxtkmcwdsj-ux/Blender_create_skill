# Delivery Procedures

## Editable Blender file

- Save a final static `.blend` and, when needed, a separate cinematic `.blend`.
- Keep semantic collections, meaningful object names, editable modifiers, and accepted materials.
- Pack images only after candidate acceptance.
- Retain stage checkpoints outside the final file.

## GLB

1. Duplicate the static delivery file.
2. Remove or exclude reference planes, diagnostics, helper lines, and unsupported effects.
3. Convert text only when compatibility requires it and preserve a source checkpoint.
4. Validate normals, transforms, hierarchy, UVs, PBR materials, images, lights, and dimensions.
5. Export GLB.
6. In a separate background Blender process, clear a temporary scene, import the GLB, and run `scripts/validate_glb.py`.
7. Report missing or unsupported features honestly.

Cycles compositor effects, volumes, rain particles, some procedural nodes, and cinematic lighting cannot be expected to reproduce exactly in GLB. Bake compatible textures only in a separately approved stage.

## Video

- Work in a cinematic copy so camera keyframes do not contaminate the static model.
- Confirm duration, fps, resolution, camera style, and codec.
- Preview key frames and run camera-collision checks.
- Render an image sequence first.
- Encode with Blender or FFmpeg only after all frames exist.
- Verify frame count, duration, resolution, codec, and playback.

## Local web preview

- Use a local Three.js installation and official `GLTFLoader` and `OrbitControls` when requested.
- Avoid CDNs when the delivery must be offline.
- Provide loading progress, error handling, reset camera, resize handling, and optional visibility toggles.
- Serve through a local HTTP server; do not rely on `file://` module loading.
- Keep web-only visibility controls separate from the GLB data.
