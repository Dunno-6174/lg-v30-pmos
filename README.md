# LG V30 (joan) — postmarketOS port

Downstream (LineageOS 4.4 kernel) port of postmarketOS for the LG V30
(MSM8998, US998/joan), plus tooling and notes from the mainline bring-up
attempt.

## Contents

| Path | What |
|---|---|
| `device/` | pmOS device package (`device-lg-joan`: deviceinfo, kernel cmdline) |
| `kernel/` | kernel package `linux-lg-joan` (APKBUILD, config, 8 patches) |
| `tools/mkboot.sh` | build a flashable `boot.img` from the kernel apk |
| `tools/ramdisk-real.gz` | known-good pmOS initramfs / cmdline used for the boot image |
| `tools/bt/` | userspace WCN3990 H4 <-> vhci bridge + helpers |
| `device-tree/` | downstream DT extracted from the running device + mainline WIP DTS |
| `mainline/` | mainline 6.0 kernel package, joan DTS, issue draft |
| `docs/` | README of the device port + full debug history (`NOTES.md`) |

## Flashable images (release assets)

- `boot.img` — downstream kernel r28 (BT + WiFi probe patches)
- `rootfs.img.gz` — pmOS root filesystem (flash to `userdata`)

```sh
fastboot flash boot boot.img
fastboot flash userdata rootfs.img     # gunzip first
fastboot reboot
```

Default login: `user` / `147147`, SSH over USB net at `172.16.42.1`.

## Status

- ✅ boot, display (fbdev), touch, dashboard, terminal + on-screen keyboard
- ✅ brightness, power key / auto screen off, reboot/shutdown
- ✅ auto time sync over USB network
- ⚠️ Bluetooth: hci0 comes up via vhci bridge, but real chip firmware never
  loads (no WLFW / hci_qca), so pairing does not work
- ❌ Wi-Fi: needs Qualcomm's proprietary PeripheralManager -> wlan_pd chain
- 🚧 mainline: kernel + DTS build, but LG LK reboots before early console

See `docs/NOTES.md` for the whole investigation and `mainline/issue-for-msm8998.md`.
