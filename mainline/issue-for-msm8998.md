# LG V30 (joan) mainline: kernel reboots before console on stock LG LK

## Device
- LG V30 US998 (msm8998 v2.1), unlocked bootloader (stock LG LK/aboot)
- Commit: 90169e6e9fee29fae14aeac0a905246be5ce6304 (6.0)
- DTS: based on `msm8998-mtp.dts`, changed to `qcom,msm-id = <292 0x20001>`,
  `qcom,board-id = <0xc08 0>` so LG LK selects it; simplefb added.

## Boot image
- `mkbootimg` v0: `Image.gz` + appended DTB, pmOS initramfs, cmdline
  `console=tty0 ... pmos_root_uuid=...`
- Same method with the **downstream 4.4 kernel** boots fine.

## Symptoms
- LG logo, then reboot loop.
- No fbcon output (simple-framebuffer node present), no pstore records
  (ramoops region verified working with the downstream kernel),
  no LK log in misc/logfs.

## Tried (all reboot before pstore, i.e. < ~0.4s)
- mainline kernel + downstream DTB
- mainline kernel + joan DTB
- gzip and uncompressed Image
- `maxcpus=1 nokaslr`
- `text_offset = 0x80000` (both gzip and uncompressed)
- `console=tty0` only (no ttyMSM0)
- VA_BITS 39 and 48
- PSTORE_RAM/PSTORE_CONSOLE with ramoops DT node

## Question
Is there a known incompatibility between mainline msm8998 and LG's LK
(image placement / text_offset / PSCI / early console)? What would be the
recommended way to get early boot output on this device?
