---
name: aosp-security
description: |
  AOSP Part IX — Security. Use when reasoning about SELinux on Android,
  Keystore/Keymint, Trusty TEE, gatekeeper/weaver, Android Verified Boot,
  dm-verity, hardware-backed attestation, Credential Manager (CredentialManagerService,
  credential providers, passkeys/FIDO2, password and autofill integration,
  digital credentials), or DRM (MediaDrm framework, Widevine L1/L2/L3,
  OEMCrypto, license acquisition, secure decoder/display path), or the LFI
  in-process sandbox (Lightweight Fault Isolation for untrusted code such as
  software codecs). Chapters 40–42, 68.
metadata:
  author: 'utzcoz'
  last-updated: '2026-06-23'
---

# AOSP Part IX — Security

Trust roots, key storage, credential management, and content protection.

## Chapters in this Part

- `40-security.md` — SELinux on Android, Keystore/Keymint, Trusty TEE, gatekeeper/weaver, AVB, dm-verity, hardware-backed attestation
- `41-credential-manager.md` — CredentialManagerService, credential providers, passkeys/FIDO2, password and autofill integration, digital credentials
- `42-drm.md` — MediaDrm framework, Widevine L1/L2/L3, OEMCrypto, license acquisition, secure decoder/display path
- `43-lfi-sandbox.md` — Lightweight Fault Isolation: memory-safe in-process sandboxing for untrusted code (software codecs) without a separate process; the external/lfi verifier and runtime, the Soong LFI toolchain, and the libapexcodecs/codec2 integration

## When to load which chapter

- Question mentions SELinux, Keystore, Keymint, Trusty, gatekeeper, weaver, AVB, attestation → `40-security.md`
- Question mentions Credential Manager, passkeys, FIDO2, autofill, digital credentials → `41-credential-manager.md`
- Question mentions MediaDrm, Widevine, OEMCrypto, secure decoder, license server → `42-drm.md`
- Question mentions LFI, lightweight fault isolation, in-process sandboxing, sandboxed software codec → `43-lfi-sandbox.md`
