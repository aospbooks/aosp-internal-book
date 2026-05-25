---
name: aosp-part-native-services-and-media
description: |
  AOSP Part IV — Native Services & Media. Use when reasoning about
  surfaceflinger, audioserver, mediaserver, cameraserver, the graphics
  pipeline (BufferQueue, GraphicBuffer, OpenGL ES / Vulkan / Skia / HWUI,
  RenderThread, layer composition), the animation system (Choreographer,
  ValueAnimator, RenderNode animations, dynamic spring/fling), the audio
  stack (AudioFlinger, AudioPolicyManager, AAudio, OpenSL ES, Spatializer),
  the media pipeline (MediaCodec, MediaExtractor, NuPlayer, codec2 HAL),
  or the sensor stack (SensorService, sensor HAL, batching, wake-up sensors).
  Chapters 12–17.
metadata:
  author: 'utzcoz'
  last-updated: '2026-05-25'
---

# AOSP Part IV — Native Services & Media

The native daemons that run continuously and own audio, video, sensors, and
the graphics composition pipeline.

## Chapters in this Part

- `12-native-services.md` — surfaceflinger, audioserver, mediaserver, cameraserver process layout, init triggers, AIDL boundaries, HAL clients
- `13-graphics-render-pipeline.md` — SurfaceFlinger, BufferQueue, GraphicBuffer, OpenGL ES / Vulkan / Skia / HWUI, RenderThread, layer composition
- `14-animation-system.md` — Choreographer, ValueAnimator/ObjectAnimator, RenderNode animations, dynamic animation, shared-element transitions
- `15-audio-system.md` — AudioFlinger, AudioPolicyManager, audio HAL, AAudio/OpenSL ES, spatial audio (Spatializer), routing rules
- `16-media-and-camera.md` — MediaCodec, MediaExtractor, NuPlayer, codec2 HAL, camera service, image/video pipeline overview
- `17-sensors.md` — SensorService, sensor HAL, batching, wake-up sensors, FIFO and event delivery, sensor fusion

## When to load which chapter

- Question is about which native daemons exist or how they boot → `12-native-services.md`
- Question mentions SurfaceFlinger, BufferQueue, GraphicBuffer, OpenGL/Vulkan/Skia/HWUI, RenderThread, composition → `13-graphics-render-pipeline.md`
- Question mentions Choreographer, animator classes, RenderNode animations, springs/flings → `14-animation-system.md`
- Question mentions AudioFlinger, AudioPolicyManager, AAudio, OpenSL ES, Spatializer → `15-audio-system.md`
- Question mentions MediaCodec, MediaExtractor, NuPlayer, codec2, camera service → `16-media-and-camera.md`
- Question mentions sensors, SensorService, wake-up sensors, batching → `17-sensors.md`
