---
name: aosp-part-security
description: |
  AOSP Part IX — Security. Use when reasoning about SELinux on Android,
  Keystore/Keymint, Trusty TEE, gatekeeper/weaver, Android Verified Boot,
  dm-verity, hardware-backed attestation, Credential Manager (CredentialManagerService,
  credential providers, passkeys/FIDO2, password and autofill integration,
  digital credentials), or DRM (MediaDrm framework, Widevine L1/L2/L3,
  OEMCrypto, license acquisition, secure decoder/display path). Chapters 40–42.
metadata:
  author: 'utzcoz'
  last-updated: '2026-05-25'
---

# AOSP Part IX — Security

Trust roots, key storage, credential management, and content protection.

## Chapters in this Part

- `40-security.md` — SELinux on Android, Keystore/Keymint, Trusty TEE, gatekeeper/weaver, AVB, dm-verity, hardware-backed attestation
- `41-credential-manager.md` — CredentialManagerService, credential providers, passkeys/FIDO2, password and autofill integration, digital credentials
- `42-drm.md` — MediaDrm framework, Widevine L1/L2/L3, OEMCrypto, license acquisition, secure decoder/display path

## When to load which chapter

- Question mentions SELinux, Keystore, Keymint, Trusty, gatekeeper, weaver, AVB, attestation → `40-security.md`
- Question mentions Credential Manager, passkeys, FIDO2, autofill, digital credentials → `41-credential-manager.md`
- Question mentions MediaDrm, Widevine, OEMCrypto, secure decoder, license server → `42-drm.md`
