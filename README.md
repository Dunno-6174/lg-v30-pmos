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

## Links

- Release (images): https://github.com/Dunno-6174/lg-v30-pmos/releases/tag/v1
- Upstream mainline issue: https://github.com/msm8998-mainline/linux/issues/2

## Flashable images (release assets)

Release: https://github.com/Dunno-6174/lg-v30-pmos/releases/tag/v1

### 中文

1. 下载 `boot.img` 和 `rootfs.img.gz`
2. 解压：`gunzip rootfs.img.gz`
3. 手机关机，按住**音量下键**插 USB，进入 fastboot
4. 刷入：

   ```sh
   fastboot flash boot boot.img
   fastboot flash userdata rootfs.img
   fastboot reboot
   ```
5. 首次启动自动扩容根分区
6. 默认账号 `user` / `147147`，USB 网络 SSH：`ssh user@172.16.42.1`

> ⚠️ 刷 `userdata` 会清空所有数据。

### English

1. Download `boot.img` and `rootfs.img.gz`
2. `gunzip rootfs.img.gz`
3. Power off, hold **Volume Down** while plugging USB to enter fastboot
4. Flash:

   ```sh
   fastboot flash boot boot.img
   fastboot flash userdata rootfs.img
   fastboot reboot
   ```
5. Root filesystem is expanded automatically on first boot
6. Login `user` / `147147`; SSH over USB net: `ssh user@172.16.42.1`

> ⚠️ Flashing `userdata` wipes all data on the phone.

## Status

- ✅ boot, display (fbdev), touch, dashboard, terminal + on-screen keyboard
- ✅ brightness, power key / auto screen off, reboot/shutdown
- ✅ auto time sync over USB network
- ⚠️ Bluetooth: hci0 comes up via vhci bridge, but real chip firmware never
  loads (no WLFW / hci_qca), so pairing does not work
- ❌ Wi-Fi: needs Qualcomm's proprietary PeripheralManager -> wlan_pd chain
- 🚧 mainline: kernel + DTS build, but LG LK reboots before early console

See `docs/NOTES.md` for the whole investigation and `mainline/issue-for-msm8998.md`.
