---
name: aosp-part-connectivity
description: |
  AOSP Part VIII — Connectivity. Use when reasoning about Networking
  (ConnectivityService, Wi-Fi framework, netd, DNS resolver, VPN, tethering,
  NetworkSecurityConfig, VCN, Thread mesh), Telephony (TelephonyManager,
  PhoneInterfaceManager, RIL/RILD, modem AIDL, IMS framework, emergency
  calling), Bluetooth (Bluetooth Mainline module, BTA, GATT, A2DP/HFP/AVDTP,
  LE Audio, pairing, scanning, advertising), NFC (NfcAdapter/NfcService,
  NCI, tag dispatch, HCE, secure element, reader mode, NFC-F/V), or USB &
  ADB (USB gadget framework, host-mode USB, MTP/PTP, RNDIS tethering, adb
  daemon, adb over Wi-Fi). Chapters 35–39.
metadata:
  author: 'utzcoz'
  last-updated: '2026-06-07'
---

# AOSP Part VIII — Connectivity

The radios, transports, and IPC stacks that move bits off the device:
Wi-Fi, cellular, Bluetooth, NFC, and USB/ADB.

## Chapters in this Part

- `35-networking.md` — ConnectivityService, Wi-Fi framework, netd, DNS resolver, VPN, tethering, NetworkSecurityConfig, VCN, Thread mesh
- `36-telephony.md` — TelephonyManager, PhoneInterfaceManager, RIL/RILD, modem AIDL, IMS framework, emergency calling, call routing
- `37-bluetooth.md` — Bluetooth Mainline module, BTA layer, GATT, A2DP/HFP/AVDTP, LE Audio, pairing, scanning, advertising
- `38-nfc.md` — NfcAdapter/NfcService, NCI, tag dispatch, HCE, secure element, reader mode, NFC-F (FeliCa) and NFC-V
- `39-usb-adb.md` — USB gadget framework, host-mode USB, MTP/PTP, RNDIS tethering, adb daemon, adb over Wi-Fi, transports

## When to load which chapter

- Question mentions ConnectivityService, Wi-Fi, netd, DNS, VPN, tethering, VCN, Thread → `35-networking.md`
- Question mentions Telephony, modem, RIL, IMS, emergency call → `36-telephony.md`
- Question mentions Bluetooth, BTA, GATT, A2DP, HFP, LE Audio, pairing → `37-bluetooth.md`
- Question mentions NFC, NCI, HCE, tag dispatch, secure element → `38-nfc.md`
- Question mentions USB gadget, MTP, RNDIS, adb, adb over Wi-Fi → `39-usb-adb.md`
