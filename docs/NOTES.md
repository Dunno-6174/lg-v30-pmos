# 屏幕驱动调试笔记（2026-10-22）

## 已确认的事实

- 当前可用系统：内核 **无 VT**（`CONFIG_VT` 未设置），fb0/fb1/fb2 = `mdssfb_90000` 等，
  没有 DRM（`/dev/dri` 不存在），屏幕能显示 pmOS 启动 logo，但没有控制台/图形界面。
- **VT + fbcon 内核会导致启动失败**：把带 `CONFIG_VT=y`、`CONFIG_FRAMEBUFFER_CONSOLE=y` 的内核
  刷入 boot 分区后，手机进入重启循环，USB 网络/SSH 都不出现；刷回无 VT 内核立即恢复。
  - 测试用的镜像是 `boot-vt-test.img`（cmdline 已去掉 `console=tty0`，仍失败）。
  - 失败时无串口日志可看（ttyMSM0 需要拆机 UART），pstore 也没留下记录（ramoops 未配置或已被清空）。
- 内核 4.4.302（LG msm8998 downstream），配置与 LineageOS 的 `lineageos_joan_defconfig` 仅差
  VT/fbcon 相关项（已用 IKCONFIG 对比验证）。
- `console=tty0` 在 cmdline 中也可能参与崩溃，但目前无法区分是 fbcon 还是 tty0。

## 明天可尝试的方向（按优先级）

1. **X11 + fbdev（不依赖 VT）**
   - `apk add xorg-server xf86-video-fbdev xf86-input-evdev xinit xterm`
   - 用 `xinit /usr/bin/xterm -- :0 -config /etc/X11/xorg.conf`，Device 段用 `fbdev`，Input 用 evdev。
   - 屏幕 1440x2880（fb0 virtual_size 1440x5760，split_mode 1，left/right 各 720）。
2. **fbterm**：`apk add fbterm`，在 fb0 上开一个终端（需要键盘/触摸输入）。
3. **VT 但关闭 fbcon**（`CONFIG_VT=y`、`FRAMEBUFFER_CONSOLE=n`）：确认 VT 本身是否安全；
   若安全，再考虑给 tty1 找独立的 fb 后端。
4. **VT + fbcon 的规避参数**：`fbcon=nodefer`、`fbcon=map:0`、`fbcon=rotate:0` 等，
   用 `fastboot boot` 或刷 boot 分区测试。
5. **抓崩溃日志**：尝试打开 pstore/ramoops（检查 DTB 是否有 `ramoops` 节点），
   或在 initramfs 里加早起的 USB ACM console（`boot-debug-novt.img` 已有类似思路）。

## 本目录文件

- `boot-vt-test.img`：带 VT 的内核 + 原 initramfs（会崩溃，仅供测试/复现）
- `boot-debug-novt.img`：无 VT 内核 + `pmos.debug-shell`（USB ACM 调试 shell，可用）
- `vmlinuz-vt`：带 VT 的内核镜像（`Image.gz-dtb`）

## 2026-10-22 晚：屏幕点亮记录

### 结论：fbdev 直接写屏完全可用

- `/dev/fb0`：1440×2880 可见，`virtual_size=1440,5760`（双缓冲），32bpp，stride 5760。
- **`write()` 到 `/dev/fb0` 返回 ENODEV**，必须用 `mmap`（Python `mmap.mmap` 即可）。
- **像素字节序是 RGBA**（不是 BGRA）：按 BGRA 写会红蓝互换。
- 显示正常、无缩放/错位；`msm-fb-refresher` 服务负责刷新。
- 背光：`/sys/class/leds/lcd-backlight`、`lcd-backlight-ex`，max=511；写 4095 会被钳到 511。
  最终用 180（约 35%）比较舒服；脚本启动时自动设置。

### 屏幕仪表盘 fbdash（当前 UI）

- `/usr/local/bin/fbdash.py`：Pillow 绘制，每秒把 1440×2880 图像 mmap 写入 fb0（写两份覆盖双缓冲）。
- 开机自启：`/etc/local.d/fbdash.start`（openrc 的 local 服务）。
  直接做成 openrc service 在启动早期不可靠（status 一直是 stopped），local.d 方式稳定。
- 留言：`echo "..." | sudo tee /run/fbdash-message`，下一秒刷新到屏幕。

### X11 尝试失败

- 已装 `xorg-server`、`xf86-video-fbdev`、`xf86-input-evdev`、`xterm`、`twm`。
- `Xorg -configure` / 指定 `fbdev` 均报 **“No devices detected”**，驱动 `FBDevProbe` 没有拿到 entity；
  fb ioctl（FBIOGET_VSCREENINFO/FSCREENINFO）本身是正常的，怀疑是 Xorg 21.1 平台总线/udev 匹配问题。
- `Xorg -novtswitch -sharevts` 也无法绕过（探测阶段就失败）。
- 后续可试：更老的 Xorg、kdrive `Xfbdev`、或自己写 fbdev UI。

### 触摸不可用

- `/proc/bus/input/devices` 只有 qpnp_pon、fingerprint、gpio-keys，**没有触摸屏 input 设备**。
- 内核日志显示 `[Touch] ... d.power is POWER_OFF`，LG ftm4 触摸驱动没有真正上电/初始化，
  可能缺面板/触摸固件或需要额外上电时序。
- 因此当前 UI 只能通过 SSH 控制，不能触摸操作。

### 下一步

- 触摸上电（ftm4 驱动、固件、面板供电时序）
- 让 Xorg/fbdev 或 kdrive 跑起来，或继续扩展 fbdash（显示日志/终端内容）
- Wi-Fi 固件（从 LineageOS 提取 wlan 固件）

## 2026-10-22 晚：触摸点亮记录

### 结论：触摸完全可用（不需要额外固件文件）

- `/proc/bus/input/devices` 中出现 `Name="touch_dev"`，`Handlers=... event1 ...`。
- 内核驱动：`CONFIG_LGE_TOUCH_STM_FTM4=y` + `CONFIG_LGE_TOUCH_CORE=y`，
  启动日志显示 STM FTM4 IC、固件 v1.11、panel rev 等，固件由内核内置/自动加载
  （`/lib/firmware/touch/joan` 实际不存在，但驱动读到了 116776 字节固件）。
- 事件格式：多点触控协议 B
  - `ABS_MT_POSITION_X` (53) / `ABS_MT_POSITION_Y` (54)
  - `ABS_MT_TRACKING_ID` (57)、`ABS_MT_PRESSURE` (58)、`ABS_MT_TOUCH_MAJOR/MINOR` (48/49)
  - `BTN_TOUCH` (330) 按下/抬起
- 读取方式：`open("/dev/input/event1","rb")`，`struct.unpack("llHHi", 24 bytes)`；
  需要 root 或 input 组权限。

### fbdash 触摸按钮

- 4 个按钮：SSH 信息、内核日志、调暗、重启（重启慎点）。
- 触摸坐标是屏幕坐标（0..1439 × 0..2879），无需缩放。
- 画面只在内容变化时重绘，解决双缓冲写入导致的按钮/计数闪烁。
- 中文必须用 CJK 字体（已装 `font-wqy-zenhei`，`wqy-zenhei.ttc`）。

### Xorg/fbdev 仍然失败（桌面路线未通）

- 症状：`(EE) No devices detected`，`FBDevProbe` 直接返回 0，甚至没有对 `/dev/fb0` 发 ioctl。
- strace 显示 Xorg 打开了 `/dev/fb0`，随后 `readlink /sys/class/graphics/fb0/device/subsystem` 失败
  （该 sysfs 没有 `device` 链接），之后放弃。
- 已试：最小 xorg.conf、`Option "fbdev"`、关闭 AutoAddDevices、`-novtswitch -sharevts`、
  bind-mount 伪造 `device` 目录（sysfs 不能创建挂载点，失败）。
- 结论：Xorg 21.1 的 fbdev 驱动在这台机器的 fb 设备上探测不到 entity；
  下一步可考虑：老版 Xorg / kdrive Xfbdev（Alpine 未打包）/ 给驱动打补丁 / 放弃 X11 做自绘 UI。

## 2026-10-22 深夜：触摸桌面（B 方案）

### 结构

- `fbdash.py` 升级为两页：`home`（仪表盘 + 按钮）和 `term`（终端 + 屏幕键盘）。
- 终端：`pty.fork()` + `execv("/bin/sh","-i")`，`TERM=dumb`，父进程非阻塞读 master。
- 键盘：屏幕坐标网格，字母/数字/符号两页；Esc、方向键（`\x1b[A/B/C/D`）、Tab、Ctrl（下一次按键转控制码）、退格（`\x7f`）、回车（`\r`）。

### 踩的坑

1. 用 `subprocess.Popen(pty_slave)` + `setsid` 时 shell 没有控制终端，输出异常；
   改用 `pty.fork()` 后正常。
2. 最初把 `\r` 当作“清空当前行”，把命令输出全擦了；改为维护光标位置（`\r` 只回到行首，字符覆盖写）。
3. 两个 fbdash 实例同时写 fb 会闪；`local.d` 启动脚本用锚定的 `pkill -f "^/usr/bin/python3 /usr/local/bin/fbdash.py$"` 保证单实例。
4. 中文标签必须用 CJK 字体（wqy-zenhei），DejaVu 会显示豆腐块。

### 其他

- 振动：内核未提供 `/sys/class/timed_output/vibrator` 或 leds 振动节点（只有 DT 节点 `vibrator@fd8c3420`），
  当前无法做触摸振动反馈，需要另开驱动/配置。
- 重启/关机按钮已实现（`os.system("reboot"/"poweroff")`），未实际测试（避免打断会话）。
- `/dev/uinput` 存在（`CONFIG_INPUT_UINPUT=y`），以后可用它注入触摸事件做自动化测试。

## 2026-10-22 晚：Wi-Fi / 蓝牙调研（未打通）

### 硬件/驱动结论

- 平台是 **WCN3990**（DT: `qcom,icnss@18800000`、`bt_wcn3990`），不是 QCA6174 PCIe。
- WLAN：`CONFIG_QCA_CLD_WLAN` + `CONFIG_ICNSS`，内置时启动只打印
  `wlan_hdd_state wlan major(225) initialized`，**不会创建 wlan0**。
- 蓝牙：UART 是 `/dev/ttyHS0`（驱动 `CONFIG_SERIAL_MSM_HS=y` 已有），
  Android 侧用 `/vendor/bin/hw/android.hardware.bluetooth@1.0-service-qti` + `libbt-vendor`。

### 已准备好的文件

- 从 LineageOS 的 system 分区（`/dev/disk/by-partlabel/system`，挂载到 `/mnt/sys`）提取：
  - WLAN：`/system/vendor/etc/wifi/{bdwlan.bin,WCNSS_qcom_cfg.ini}` →
    `/lib/firmware/wlan/qca_cld/`
  - BT：`/system/vendor/etc/firmware/{rampatch_tlv_*.tlv,nvm_tlv_*.bin}`、
    `/system/vendor/firmware/{crbtfw21.tlv,crnv21.bin}` → `/etc/firmware/`
- 从 modem 分区（`/dev/disk/by-partlabel/modem`，vfat）提取：
  `wlanmdsp.mbn`、`bdwlan.*` → `/lib/firmware/`
- 已安装 `bluez`、`bluez-deprecated`（含 hciattach/btattach/hciconfig/bluetoothctl）、`iw`。

### 阻塞点（关键）

1. **打开 `CONFIG_BT_HCIUART=y` 会让内核启动早期崩溃**（重启循环）。
   - 用“只改 BT、WLAN 保持内置”的对照内核验证过，仍崩溃 → 不是 WLAN 模块的问题。
   - 该内核树的 `hci_ldisc.c` 是从新版本 backport 的，`struct hci_uart` 缺 `rx_lock`，
     已补丁（`0002-bluetooth-add-rx_lock-to-hci_uart.patch`）才能编译，但仍有运行时问题。
   - 下一步：把 `CONFIG_BT_HCIUART=m`（模块，启动后手动 modprobe，能先拿到 dmesg），
     或者彻底修 `hci_ldisc.c`/`hci_uart.h` 与新 tty API 的兼容性。
2. **WLAN 内置时不创建 wlan0**：很可能需要 Android 的 `cnss-daemon`（QMI WLFW）来加载
   `wlanmdsp.mbn`/启动 WPSS，单纯放固件不够。
   - 把 qcacld 改成模块（`=m`）的两次构建都伴随 BT 改动，尚未单独验证；
     下一步先测“只 QCA_CLD_WLAN=m、不动 BT”。
3. 另一条路：`CONFIG_BT_HCIVHCI` 也没开，否则可以做“用户态 H4 + /dev/vhci 桥接”绕过内核 HCIUART。

### 当前状态

- 已刷回可用内核（无 BT/WLAN 改动），系统正常运行。
- 实验用配置/APKBUILD 保存在 `debug/kernel-experiments/`。
- 系统里保留了 bluez/iw 和已拷贝的固件，方便下次继续。

### 追加实验（22:30-22:50）

- **只把 qcacld 改成模块（`CONFIG_QCA_CLD_WLAN=m`，BT 保持关闭）**：内核仍然启动失败
  （即使 `/lib/modules` 里没有任何模块文件、不存在 udev 自动加载）。说明是 `=m` 这个配置本身
  导致启动异常，不是模块被自动加载。
- **尝试用 ramoops/pstore 抓崩溃日志**：设备 DT 里有 `ramoops_region@b0000000`（1MiB），
  启动日志确认 `pstore: Registered ramoops`、`ramoops: attached 0x80000@0xb0000000`。
  刷入会崩的内核让它崩一次，再刷回可用内核后 `/sys/fs/pstore/` 仍为空 ——
  说明失败不是 panic（更像 hang/watchdog reset），或日志未跨过强制断电。
- 结论：在没有串口（ttyMSM0 UART）或 early console 的情况下，继续盲试内核配置成本很高。
  下一步建议先接 UART 或做一个能输出到 USB ACM 的 early console 方案。

### Early console 尝试（23:00）

方案：内置 legacy `g_serial`（`CONFIG_USB_G_SERIAL=y`）+ `console=ttyGS0`，
期望在内核 initcall 阶段（崩溃之前）就把 printk 输出到 USB ACM。

结果：**编译失败**。LG 这棵内核的 `drivers/usb/gadget/configfs.c` 是较新版本的 backport，
与旧的 `struct gadget_info` 不匹配：
`no member named 'work' / 'factory_lock' / 'dev'`，以及 `gadget_index` 未声明。
`configfs.o` 是 `libcomposite` 的一部分，而 `g_serial`/`f_acm` 依赖它，所以这条路被卡住。

可选出路：
1. 修 `configfs.c` 的 backport（给 `struct gadget_info` 补字段/全局变量），让 `libcomposite` 能编译；
   然后把 `g_serial` 内置 + `console=ttyGS0`，就能拿到 initcall 阶段的日志。
2. 用模块方式加载 `g_serial`（只能覆盖 initramfs 之后的崩溃，抓不到当前这种早期崩溃）。
3. 硬件 UART（ttyMSM0）仍然是最可靠的办法。

### Early console 实验结论（23:00-23:25）

- 修好了 `configfs.c` 在 `CONFIG_USB_CONFIGFS_UEVENT` 关闭时的编译问题
  （补 `struct gadget_info` 字段和 `gadget_index`，补丁 `0003-configfs-build-without-uevent.patch`）。
- 但内置 legacy gadget（`g_serial`、`g_zero`）的内核**运行期仍然启动失败**：
  USB 上只出现 LK 的 fastboot 设备，从未出现 0525:xxxx 的 gadget 设备。
- 本地复现 defconfig 解析还发现：legacy gadget 与 configfs 在 tristate choice 里互斥，
  很容易被解析成“没有任何 gadget”，initramfs 的 USB 网络也随之失效。
- 结论：这棵内核的 USB gadget/composite 代码是“新 backport + 旧结构体”的半成品，
  做 USB ACM early console 成本过高、不可靠。**建议改用硬件 UART（ttyMSM0）**，
  或写一个完全绕开 composite 的极简 raw-gadget ACM 驱动（工作量大）。

## 2026-10-23 凌晨：重要更正 + 新进展

### 关键 bug：boot 镜像 ramdisk 提取偏移错误

之前所有"内核启动失败"的结论都是假的：提取 ramdisk 时用了 `d[ps:ps+rs]`，
这取到的是内核 gzip 数据，不是 initramfs。正确偏移：

```
off = ps + roundup(kernel_size, ps)   # ps = page size (4096)
ramdisk = boot_img[off:off+ramdisk_size]
```

校验：gunzip 后应包含 `070701`（cpio）。修正后用 r17 内核重打包，正常启动。

**之前关于 BT HCIUART / WLAN=m / g_serial / g_zero 导致启动崩溃的结论全部作废。**

### 蓝牙：UART 已通，卡在固件下载

- r5 内核（HCIUART=y+H4）启动正常。
- `hciattach /dev/ttyHS0 qualcomm 3000000 flow` 能读到
  `Qualcomm module LMP version : 0x08 / sub-version : 0x02be` → 芯片有应答。
- 之后它尝试打开固件 `/lib/firmware/201 PF_ BUI.bin`（明显是乱码文件名），失败。
- `btattach -P h4 -S 115200` 能建 hci0，但 BD address 全 0、无 features（芯片未初始化）。
- `btattach -P qca -S 3000000`（r3 内核，带 HCIUART_QCA）建了 hci0 但 TX 10/RX 0，
  随后 hciconfig 卡死 —— 内核 hci_qca 这条 backport 路径不可靠。

### Wi-Fi：模块能加载，但没有 wlan0

- r3 内核（QCA_CLD_WLAN=m）启动正常；安装 `wlan.ko` 后 `modprobe wlan` 成功，
  日志出现 `wlan_hdd_state wlan major(220) initialized`。
- 但没有 `wlan0`，icnss 的 WLFW QMI 计数器全 0（`/sys/kernel/debug/icnss/stats`），
  说明固件/WPSS 没有被启动 —— 这正是 Android 里 `cnss-daemon` 干的活。
- 固件文件已就位：`/lib/firmware/wlan/qca_cld/*`、`wlanmdsp.mbn`、`bdwlan.*`。

### 下一步选项

1. 蓝牙：写用户态 QCA 固件下载 + `/dev/vhci` 桥接（需要开 `CONFIG_BT_HCIVHCI=m`），
   绕开内核 hci_qca；或者修 hciattach 的固件文件名逻辑。
2. Wi-Fi：移植/实现最小 cnss WLFW 触发（QMI），或找到 Android cnss-daemon 的可移植替代。
3. 硬件 UART（CH340）仍是最可靠的调试手段，但需要主板测试点照片。

## 恢复 / 继续工作的入口（2026-10-23）

### 正确的 boot 镜像打包方法

`/tmp` 重启会丢，所有需要的东西已放到 `tools/`：

- `tools/ramdisk-real.gz`：从可用 `boot.img` 正确提取的 pmOS initramfs（gunzip 后是 cpio）
- `tools/cmdline.txt`：可用的内核 cmdline（pmos_root_uuid=6c972a82-...）
- `tools/mkboot.sh`：从 pmbootstrap 的 kernel apk 直接生成可刷 boot 镜像

用法：

```bash
cd lg-v30-postmarketos
./tools/mkboot.sh ~/.local/var/pmbootstrap/packages/edge/aarch64/linux-lg-joan-4.4.302-r5.apk /tmp/boot-r5.img
fastboot flash boot /tmp/boot-r5.img
```

校验 ramdisk 是否正确的唯一标准：`gunzip -c ramdisk | head -c 6` 应该是 `070701`。

### 现有内核包（~/.local/var/pmbootstrap/packages/edge/aarch64/）

| 包 | 配置要点 | 用途 |
|---|---|---|
| linux-lg-joan-4.4.302-r1.apk | 原始可用内核（VT 关、QCA_CLD=y、无 BT） | 基线；对应仓库 `boot.img` |
| r3 | `HCIUART=y` + `HCIUART_QCA=y` + `QCA_CLD_WLAN=m` | 蓝牙 QCA 协议 + wlan.ko（当前手机跑的） |
| r5 | `HCIUART=y` + `HCIUART_H4=y` + `QCA_CLD_WLAN=y` | 蓝牙 H4 测试 |
| r7 | `QCA_CLD_WLAN=m`，BT 关 | Wi-Fi 模块测试 |
| r15 | 基线 + panic 画屏补丁 | panic 时把日志画到屏幕（待验证） |
| r17 | 基线 + 只有 dummycon 补丁 | 证明“启动失败”是 ramdisk 问题的对照 |

kernel apk 里没有 `data.tar.gz`，直接 `tar xzf xxx.apk` 即可得到 `boot/vmlinuz` 和 `usr/lib/modules/`。

### 当前手机状态

- 运行 **r3** 内核（BT QCA + WLAN=m）；SSH、触摸桌面正常
- `/lib/modules/4.4.302-perf` 里已装 wlan.ko，当前已 modprobe（无 wlan0）
- 如要回到基线：`fastboot flash boot boot.img`（仓库根目录）

### 明晚继续的顺序建议

1. **蓝牙**：优先写用户态方案
   - 开 `CONFIG_BT_HCIVHCI=m`（内核），用 `/dev/vhci` + Python 做 H4 桥接
   - 在用户态完成 QCA 固件下载（`crbtfw21.tlv`/`crnv21.bin` 或 `rampatch_tlv_3.2.tlv`/`nvm_tlv_3.2.bin`），
     可完全绕开内核 hci_qca/hciattach 的固件文件名 bug
   - 或者先修 hciattach qualcomm 打开固件路径的逻辑（它拼出了乱码文件名）
2. **Wi-Fi**：icnss 的 WLFW QMI 计数器为 0，需要触发 WPSS 固件加载
   - 先试模块参数（`/sys/module/wlan/parameters/*`）
   - 再考虑最小 cnss/WLFW QMI 实现，或找可移植的 cnss-daemon
3. **调试基建**：r15 的 panic 画屏可以用正确 ramdisk 重打包验证一次；
   如果可用，以后内核崩溃直接看屏幕

## 2026-10-24 晚：蓝牙打通 ✅

### 结论

- 芯片是 **WCN3990（Cherokee）**：`crbtfw21.tlv` / `crnv21.bin`，ROM 版本 0x21。
- 内核 4.4 的 `hci_qca`（Rome 专用）+ `hciattach qualcomm` 都不适配它；
  直接走内核 hci_uart 会卡死或固件下载失败。
- **可用方案：用户态 H4 ↔ /dev/vhci 桥接**
  1. 内核开 `CONFIG_BT_HCIVHCI=m`（r18 内核），`modprobe hci_vhci` 得到 `/dev/vhci`
  2. `bth4vhci.py` 把 `/dev/ttyHS0` 的 H4 包（含类型字节）与 `/dev/vhci` 双向转发
  3. BlueZ 看到普通 hci0（Bus: Virtual），芯片的 ROM 固件足以完成扫描/连接
  4. 桥接里对 HCI_RESET 做了兜底：0.5s 无响应就注入 Command Complete

### 关键坑

- **rfkill 软阻塞**：`bt_power` 和 `hci0` 默认 soft-blocked，必须 `rfkill unblock bluetooth`
- **芯片上电慢**：启动后需要等它响应 HCI（`btwait.py` 轮询 reset/version，最多 120s），否则 hci0 停在 DOWN
- 桥接必须用 `setsid` 常驻（普通 nohup 会随 SSH 会话退出）
- `/dev/vhci` 只有 root 可读写，桥接以 root 运行
- 每次重启最好 `rmmod/modprobe hci_vhci`，保证设备号是 hci0

### 已部署

- `/usr/local/bin/bth4vhci.py`、`/usr/local/bin/btwait.py`
- `/etc/local.d/bt.start`：rfkill unblock → modprobe → 等芯片就绪 → 起桥 → 起 bluetoothd → power on
- 验证：重启后 `hciconfig hci0` 为 UP RUNNING，`bluetoothctl scan on` 能扫到多个设备
- 对应的内核包：`linux-lg-joan-4.4.302-r18.apk`（`BT_HCIVHCI=m`，WLAN 仍内置），
  boot 镜像 `tools/boot-r18-bt-vhci.img`

## 2026-10-24 晚：Wi-Fi 尝试（ath10k 路线，未通）

### 发现

- DT 节点 `soc/qcom,msm_ath10k_wlan` 的 compatible 是 **`qcom,wcn3990-wifi`**，
  且这棵 4.4 内核**自带 ath10k SNOC 驱动**（`drivers/net/wireless/ath/ath10k/snoc.c`，
  `CONFIG_ATH10K_TARGET_SNOC` / `ATH10K_SNOC`），是比 qcacld 更干净的 mainline 路线。
- 但该节点默认 `status = "disabled"`（Android 走 qcacld/icnss，不用 ath10k）。
- 已做的修改：
  - `0005-cfg80211-add-ieee80211-band-aliases.patch`：补上本树 cfg80211 缺失的
    `IEEE80211_BAND_*` 别名（mac80211/ath10k 需要）
  - 二进制改 DTB：把 10 个 DTB 里 ath10k 节点的 status 从 `disabled` 改成 `okay`
  - 内核 r21：`QCA_CLD_WLAN=n`、`MAC80211=m`、`ATH10K=m`、`ATH10K_TARGET_SNOC=m`、
    `ATH10K_SNOC=y`；模块 ath10k_core/ath10k_snoc/mac80211/ath
  - 固件放 `/etc/firmware/`：`firmware-5.bin`、`board-2.bin`、`wlanmdsp.mbn`
    （Alpine `linux-firmware-ath10k` 解压后 zstd 解压）

### 结果

```
ath10k_snoc 18800000.qcom,msm_ath10k_wlan: failed to get fw ready indication
ath10k_snoc 18800000.qcom,msm_ath10k_wlan: failed to start QMI service: -14
ath10k_snoc: probe of 18800000.qcom,msm_ath10k_wlan failed with error -14
```

- 驱动能绑定到设备了，但 **WLFW QMI 服务不可用**。
- 这棵内核的 ath10k_snoc 依赖 QMI/remoteproc（`ath10k_qmi`）与 WCN3990 固件侧通信；
  而本树的 WLAN 栈是 Android 的 qcacld + icnss（icnss 也是 WLFW QMI 客户端），
  没有可用的 WLFW 服务端 / WPSS remoteproc（`drivers/remoteproc` 里没有 q6v5_wcss）。
- 结论：Wi-Fi 需要更底层的工作，二选一：
  1. 移植 mainline 的 `ath10k_qmi.c` + `qcom_q6v5_wcss`（remoteproc）到 4.4，工作量较大；
  2. 继续 Android 路线：让 icnss 拿到 WLFW 服务（需要 modem/WPSS 起来，涉及 PIL/QMI/RIL）。
- 当前 r21 内核可以启动、蓝牙仍正常（hci_vhci 桥不受影响），但 ath10k 探测失败（无害）。
  想回到纯蓝牙备份状态：`tools/boot-r18-bt-vhci.img`。

## 2026-10-24 深夜：Wi-Fi 继续（modem 起来了，WLFW 仍缺）

### 关键进展

- 写了 `modem_boot.ko`（`drivers/misc/modem_boot.c`，patch `0006-modem-boot-helper.patch`）：
  insmod 时调用 `subsystem_get("modem")`。
- 把 modem 分区 `image/*`（mba.mbn、modem.mdt、modem.bXX）拷到 `/lib/firmware`，
  insmod 后 modem **成功启动**：
  ```
  pil-q6v5-mss: modem: loading ... MBA boot done
  pil-q6v5-mss: modem: Brought out of reset
  sysmon-qmi: Connection established between QMI handle and modem's SSCTL service
  /sys/bus/msm_subsys/devices/subsys6/state = ONLINE
  ```
- 但 ath10k_snoc 仍然：
  `failed to get fw ready indication` / `failed to start QMI service: -14`
- icnss 的 WLFW 计数器仍为 0；unbind/bind icnss 报 `Driver is already initialized`。
- 结论：**WLFW QMI 服务不在 modem 上**（或需要 icnss/qcacld 自己把 WLAN 固件拉起来）。

### 两条路线的判断

- **Android 路线（icnss + qcacld，推荐）**：内核里代码齐全、就是为这台机器写的；
  现在 modem 已经能起来，缺的是按正确顺序加载 icnss/qcacld。
  把 `CONFIG_ICNSS=m`、`CONFIG_QCA_CLD_WLAN=m` 后遇到两个编译问题：
  1. `icnss.c` 里 `MODULE_DESCRIPTION(DEVICE "...")` 的 `DEVICE` 宏在 =m 时未定义
  2. qcacld 模块编译时 `struct csr_roam_profile` 缺 `MFPRequired` 等字段
     （怀疑是模块构建时少了某个 `WLAN_FEATURE_11W` 宏/包含路径）
  这两个都是可修的小问题。
- **ath10k 路线**：需要移植 `ath10k_qmi` + `qcom_q6v5_wcss`/QMI transport，工作量大。

### 当前状态

- 刷的是 r22 内核（ath10k 启用但探测失败 + modem_boot 模块），**蓝牙仍正常**
- modem 可用 `modprobe modem_boot` 拉起（约 60 秒）
- 下一步：修 icnss/qcacld 模块编译，按“modem → icnss → wlan”顺序加载

## 2026-10-24 深夜（续）：r24/r25 与 icnss 顺序问题

### 尝试记录

- r23（ICNSS=m + QCA_CLD=m）：编译失败
  - icnss.c 的 `MODULE_DESCRIPTION(DEVICE ...)` 缺 `DEVICE` 宏
  - qcacld 模块构建时 `WLAN_FEATURE_11W` 没开（`configs/default_defconfig` 里
    `ifeq (y,$(findstring y,...CONFIG_ICNSS))` 只认 `y`，`m` 不算）
- 已写 `0007-wifi-module-build-fixes.patch` 修这两处；但 r24 链接失败：
  qcacld/icnss 作为模块时，`wlfw_*_ei`、`pld_snoc_*`、`hif_check_fw_reg` 等
  符号在 vmlinux 里未导出 → 模块组合不可行（除非继续改 Kbuild/导出符号）。
- 改用 **r25：ICNSS=y（内置）+ QCA_CLD_WLAN=m（模块）**，编译成功。

### r25 实测结果

- 启动正常；`modprobe modem_boot` → modem ONLINE（约 60 秒）
- 再 `modprobe wlan` → HDD 初始化成功（`wlan_hdd_state wlan major(220) initialized`）
- **仍然没有 wlan0**，icnss 的 WLFW 计数器全 0
- 推断：icnss 在**内核启动时**（modem 还没起来）就尝试连 WLFW QMI，失败后不重试；
  Android 上 modem 由 bootloader/更早流程拉起，所以 icnss 能连上。

### 下一步（最可能有效）

给 icnss 加一个“延迟重试 QMI 连接”的机制：
- 在 icnss probe 的 QMI 连接失败时，用 delayed work 定时重试（例如每 2 秒，最多 60 次）
- 这样用户态 `modprobe modem_boot` 把 modem 拉起来后，icnss 能自动连上 WLFW，
  再 `modprobe wlan` 就能拿到 wlan0
- 需要读 icnss.c 的 probe/QMI 初始化路径，找到 `qmi_handle_create`/`qmi_add_lookup` 失败点

## 2026-10-24 深夜：电源键 / 自动熄屏

- 电源键：`/dev/input/event0`（`qpnp_pon`），EV_KEY code=116（KEY_POWER）。
- fbdash 新增：
  - `power_reader` 线程监听电源键，短按切换熄屏/亮屏
  - `screen_off()`：背光写 0 + `FBIOBLANK(4)`；`screen_on()`：`FBIOBLANK(0)` + 恢复背光 + 强制重绘
  - 30 秒无操作自动熄屏（`state["last"]` 由触摸/电源键刷新）
- 已验证：等 30 秒背光 180→0；按电源键恢复 180；再按变 0。
- 重启 fbdash：`sudo /etc/local.d/fbdash.start`，日志 `/var/log/fbdash.log`。

## 2026-10-24 深夜（再续）：WLFW 服务定位

### 新发现

- icnss **本来就支持 WLFW 服务“迟到”**：`icnss_driver_event_server_arrive()`
  在 QMI 服务到达时创建 client、连接、上电、发 ind_register/msa_info/cap。
- 我们 r25 + 手动拉起 modem 后，**没有出现 "QMI Server Connected"**
  （icnss 计数器全 0），说明 modem 并没有对外提供 WLFW 服务（service id 0x45）。
- 内核里另有 `drivers/net/wireless/cnss2/`（CNSS2，PCIe QCA6174/6290 用），
  依赖 PCI_MSM，与 WCN3990 SNOC 不匹配；DT 里也没有 cnss 节点。
- DT 里所有 `qcom,firmware-name` 只有 venus/ipa/adsp/slpi/modem/spss，**没有 wlan/wpss**。

### 结论

WLFW 服务不在 modem 上，也不在任何已启动的子系统上；它大概率运行在 WCN3990 的
WPSS 固件里，而该固件在 Android 上由 `cnss-daemon`/QMI 流程加载。
也就是说：**要么移植 cnss-daemon 等用户态流程，要么移植 mainline 的
ath10k_qmi + q6v5_wcss**；仅靠调 icnss 重试不能解决。

### 可选下一步

1. 写一个“强制周期性 lookup WLFW 服务”的 icnss 调试补丁，确认服务到底存不存在
   （成本较低，能给出明确答案）
2. 移植 mainline `ath10k_qmi` + `qcom_q6v5_wcss`（工作量大）
3. 找 Android `cnss-daemon` 源码并移植到 musl（工作量大）

## 2026-10-24 深夜（诊断结论）：WLFW 服务确实不存在

- 给 icnss 加了 `0008-icnss-wlfw-probe-retry.patch`：
  每 5 秒用临时 QMI client 尝试 `qmi_connect_to_service(WLFW, 0x45)` 并打印返回码。
- 实测（r26）：**modem 拉起前后都一直是 `connect ret=-19`（ENODEV）**，
  说明 modem 并没有对外提供 WLFW 服务，任何已启动子系统都没有。
- 结论：WCN3990 的 WPSS/WLAN 固件没有被加载，QMI WLFW 服务不存在；
  仅靠 icnss 重试无解。

### Wi-Fi 只剩两条真正的路

1. 移植 mainline `ath10k_qmi` + `qcom_q6v5_wcss`/remoteproc（自己加载 WLAN 固件）
2. 移植 Android `cnss-daemon`（由它走 QMI 把 WPSS 拉起来）

两条都不小，需要专门安排时间做。当前 r26 的日志每 5 秒会刷一条
`wlfw probe: connect ret=-19`，属预期诊断输出；想清静可刷回 r25。

## 2026-10-24 深夜：仪表盘增加内存/CPU/存储

- `fbdash.py` 新增：
  - `mem_info()`：/proc/meminfo 的 MemTotal/MemAvailable → "已用/总量 GB"
  - `disk_info()`：statvfs("/") → "已用/总量 GB"
  - `cpu_reader()` 线程：每 2 秒从 /proc/stat 算 CPU 占用，更新 state 并触发重绘
- 主页信息行改为 7 行（电池/内存/CPU/存储/运行/IP/背光），起始 y=860、行距 88。
- 截图：`screen-memcpu.png`
- 注意：系统时间显示为 2017-03-04（RTC 不保存、开机未对时），需要的话可加 chrony/NTP。

## 2026-10-24 深夜：开机自动对时

- `/usr/local/bin/timesync.sh` + `/etc/local.d/timesync.start`：
  - 先补默认路由 `ip route add default via 172.16.42.2 dev usb0`
  - 轮询 ping（203.107.6.88 / 1.1.1.1），有外网后 `ntpd -q -n -p <server>` 一次性校时
  - 依次尝试 203.107.6.88（ntp.aliyun.com）、120.25.115.20、pool.ntp.org
  - 失败每 15 秒重试，最多 240 次（约 1 小时）
- 已验证：把时间改成 2017-03-04 后重启，开机自动恢复到 2026-10-24 23:34 CST。
- 前提：USB 网络能上外网（电脑侧要开 NAT/ICS）；只连电脑没共享网络时不会校时。

## 2026-10-25 凌晨：fbdash 黑屏修复

- 现象：仪表盘黑屏，SSH 正常，背光 511，`fbdash.py` 未运行。
- 原因：手工加「我的应用」按钮时用了 Tab 缩进（与文件里的空格混用），
  Python 报 `TabError: inconsistent use of tabs and spaces in indentation`，
  `/etc/local.d/fbdash.start` 启动即失败，屏幕没有人画/没人设背光。
- 修复：把 Tab 改成 4 的倍数空格，保留用户的按钮和标题改动，重新启动。
- 加固：`/etc/local.d/fbdash.start` 增加 `python3 -m py_compile` 预检查；
  语法错误时**不再 pkill 旧实例**，只打印错误到 `/tmp/fbdash-syntax.log`。

## 2026-10-25 晚：给 WLAN 芯片上电（r28）

- r27 的补丁其实没生效（生成 patch 时 python 断言失败，后续命令仍用了旧文件），
  已重新生成并确认 kernel 里包含 `hw power on ret` 字符串。
- r28：icnss 探测线程先调用 `icnss_hw_power_on(penv)`，日志：
  ```
  icnss: wlfw probe: hw power on ret=0
  pm8998_l5: enabled, 800mV, consumer 18800000.qcom,icnss
  ```
  说明 **0.8V 核心电源和时钟已经拉起来了**。
- 但 WLFW 连接仍然是 `connect ret=-19`（ENODEV），持续每 5 秒。
- 结论：芯片上电后仍然没有 WLFW 服务 → 该服务确实来自需要另外加载的
  WPSS/WLAN 固件（`wlanmdsp.mbn`），不是芯片 ROM 自带。

### Wi-Fi 下一步（需要专门时间）

1. 移植 mainline `ath10k_qmi` + `qcom_q6v5_wcss`（由内核自己加载 WPSS 固件）
2. 或移植 Android `cnss-daemon` 的最小 QMI 流程（用户态把固件下载进芯片）

两条都是大工程；当前 r28 可以留着做实验（每 5 秒一条 probe 日志）。

## 2026-10-25 晚：可行性评估结论（重要）

对 Android 的 `cnss-daemon`（从 LineageOS system 分区提取，95KB）做了 strings 分析：

- 它只是 **QMI WLFW 客户端**：`libqmi_cci`、`qmi_client_init`、`wlfw_send_bdf_download_req`、
  `wlfw_send_mac_addr_req`、`wlfw_send_qdss_trace_*` 等
- 只访问 `/vendor/firmware_mnt/image/qdss_trace_config.cfg`，**不加载 WLAN 固件**
- 通过 `cnss-genl` netlink 和内核驱动通信

而 LG 内核里 **icnss 和 ath10k 都已经各自带了 WLFW QMI 客户端**
（`drivers/soc/qcom/icnss.c`、`drivers/net/wireless/ath/ath10k/qmi.c`），
两者都只是 `qmi_connect_to_service(WLFW, 0x45)`，等固件侧提供服务。

=> **移植 ath10k_qmi 或 cnss-daemon 都不会有用**：它们和现有的 icnss 是同一类客户端，
   缺的是 **WLFW 服务提供者（WPSS/WLAN 固件）**，也就是“谁把固件装进芯片并启动它”。

我们已经排除/确认：
- 芯片已上电（0.8V + 时钟，`hw power on ret=0`），仍无 WLFW
- modem 已 ONLINE，仍无 WLFW
- DT 无 wlan/wpss 的 PIL 节点，内核无 q6v5_wcss remoteproc
- 内核里所有 QMI 客户端都只是等这个服务

最可能的真相：WLAN 固件由 **bootloader（LK）** 或 Android 的 modem/RIL 流程加载，
这不在内核可控范围内，需要文档或抓 Android 启动日志才能确认。

### 建议

Wi-Fi 暂停，除非能拿到：
1. 这台机器 Android 启动时 `dmesg` 里 WLAN 初始化片段（能看到谁 load 固件）
2. 或 LG 的 WLAN bring-up 文档
3. 或确认 LK 是否会加载 wlan 固件（需要串口/更底层手段）

继续在 pmOS 侧改内核/QMI 客户端是无效循环。

## 2026-10-25 晚：追查“谁加载 WLAN 固件”

- `logfs` 分区（8MB FAT12）为空，没有 Android 启动日志。
- Android 的 `cnss-daemon` 只是 QMI WLFW 客户端（已确认），不加载固件。
- Android init 脚本里有 `/sys/kernel/boot_wlan/boot_wlan` 和 `wcnss-service`，
  但 **LineageOS 内核源码里根本没有 `boot_wlan` 这个驱动/文件**（全树 grep 为空），
  说明这两个是 stock LG 内核遗留，LOS 上 chown 失败也无害。
- `/vendor/lib/modules` 里没有 wlan.ko，Android 的 qcacld 也是内核内置——
  和我们的 r25/r28 是同一套栈。

结论：无法从现有分区/脚本里找到“谁加载 WCN3990 固件”的答案。
要抓 Android 启动日志，需要真正启动 Android（先格式化 data、再开 adb），
代价大且不一定有 WLAN 相关日志（recovery 模式不会跑 cnss-daemon，看不到用户态流程）。

## 2026-10-25 深夜：Android 实地取日志（重大发现）

临时刷了 LineageOS 22.2（recovery + OTA sideload），完整启动 Android 后抓了 dmesg/logcat
（保存在 `android-logs/`）。

### WLAN 固件到底是谁加载的

logcat/dmesg 关键顺序：

```
cnss-daemon 启动
cnss-daemon wlfw_start / wlfw_service_request
service-notifier: root_service_service_ind_cb:
    Indication received from msm/modem/wlan_pd (instance 180)
icnss: QMI Server Connected: state: 0x981
icnss: WLAN FW is ready: 0xd87
```

也就是说：**是 modem 侧的 `wlan_pd` 外围设备域被启动后，WLFW 服务才出现**。
而触发它的不是 QMI 客户端本身，而是 Android 用户态的
**PeripheralManager 服务**（`libperipheral_client.so` 是它的 binder 客户端，
cnss-daemon 通过 binder 调用它）——这是 Qualcomm 的专有 vendor 服务。

结论（最终）：
- icnss、ath10k、cnss-daemon 都只是 WLFW 客户端，没用
- 真正缺的是 **PeripheralManager → modem wlan_pd → WLFW** 这条专有链
- 在 pmOS 上复刻需要重写 PeripheralManager 的 QMI 协议（闭源），工作量很大

### 恢复过程（有坑）

- 先尝试恢复 `backup-2026-10-25/rootfs.img`，但**卡在 initramfs**（网络通、无 sshd、黑屏）。
  镜像本身 fsck 干净、UUID 正确、ext4 内置；怀疑 tar 方式生成的快照在 4.4 上挂载有问题
  （待进一步查，`orphan_file` 已排除：已验证的 lg-joan.img 也有该特性）。
- 最终刷回仓库里最早验证过的 `lg-joan.img` + `boot.img`，系统恢复。
- 恢复后重新部署：`fbdash.py`（含电源键/自动熄屏/内存/CPU/存储/我的应用）、
  `timesync.sh`、`py3-pillow`、`font-wqy-zenhei`；仪表盘和自动对时已恢复。
- **蓝牙/无线尚未恢复**（原镜像没有 bluez、当前内核也没有 hci_vhci 模块）。

### 待办

1. 重新刷 r18/r28 内核 + 模块，恢复蓝牙
2. 修好“tar 快照不能启动”的问题（改用 rsync 到已验证镜像，或 pmbootstrap install）
3. 更新可用备份

## 2026-10-26 凌晨：恢复失败的真正根因（已修）

**根因：备份脚本用 `tar --exclude=./proc ./sys ./dev ./run ./tmp ./var/log` 打包，
但排除了目录本身，导致快照根文件系统里根本没有这些挂载点目录。**

后果：initramfs 正常找到并挂载了 rootfs（parted/blkid 都正常），
switch_root 时 `mount --move /proc /sysroot/proc` 等失败，
切过去后没有 /proc；openrc 的 sysctl/tmpfiles 全部失败，
sshd、fbdash 起不来 → 表现为“网络通、无 SSH、黑屏”。

定位手段：给 boot.img cmdline 加 `pmos.debug-shell`，
initramfs 会在 USB 上开 telnet/ACM，进去手动 `mount`/`chroot` 复现。

修复：在快照镜像里补建 `proc sys dev run tmp var/log`（tmp 1777），
10-24 和 10-25 两份备份都已修。验证：刷回 10-25 快照后 SSH 正常、
fbdash 正常、时间已同步、根分区自动扩到 48.7G。

**以后做备份必须记得：** 排除挂载点内容后，要 `mkdir` 出空的目录，
否则快照不可启动。更好的做法是 rsync 到已验证镜像或 pmbootstrap install。

## 2026-10-26 00:27：恢复完成

- 10-25 快照修复后成功启动：SSH、fbdash、自动对时正常，根分区扩到 48.7G。
- 刷入 r28 内核（`tools/boot-r28-icnss-poweron.img`）后蓝牙恢复：
  `hci0 UP RUNNING`，BD Address 00:00:00:00:5A:AD。
- 当前系统 = 最新快照 rootfs + r28 内核。
- 注意：r28 的 icnss 探测补丁每 5 秒打一条 `wlfw probe: connect ret=-19`，
  属 Wi-Fi 诊断输出；不需要时可刷回无补丁内核（如 r25）。

## 2026-10-26 00:30：键盘 Shift/Caps + 蓝牙按钮

- `fbdash.py` 键盘新增 **Shift**（一次性大写/符号）和 **Caps**（大写锁定），
  状态 `state["shift"]/state["caps"]`；开启时键帽显示大写/符号，按钮高亮。
- 主页「我的应用」按钮改为 **「蓝牙」**，调用 `/usr/local/bin/btconnect.sh`：
  开 rfkill/hci_vhci/蓝牙电源，有已配对设备就 `bluetoothctl connect`，
  否则 `discoverable on` 并提示“可被发现”；结果显示在主页消息行。
- 脚本实测输出：`蓝牙已开启，未配对设备（可被发现）`。

## 2026-10-26 晚：蓝牙“假工作”真相 + 固件下载初探

### 关键发现：之前的“蓝牙正常”是虚拟的

- `hci_vhci` + `bth4vhci.py` 桥接层会**伪造 HCI Reset 完成事件**，
  即使 WCN3990 没有真正响应，`hci0` 也会显示 `UP RUNNING`。
- 真正的芯片 UART 通信一直没建立：iPhone 配对请求从未到达 host，
  日志里没有任何 connection/pairing 事件。
- `dmesg` 里 bt_power 驱动报：
  `bt-reset-gpio not provided in device tree`、`clock not provided in device tree`
  —— 设备树缺 BT 复位 GPIO 和时钟，芯片可能一直处于复位/未时钟状态。

### 今天修好的

- `btloadfw.py` 里的 H4 事件解析 bug（把 event code 当成了长度），
  修复后确认：开机时芯片**会响应 EDL 版本查询**
  （`ready on try 1 (version): 04ff0e...`）。
- 已把 `crnv21.bin` 的 BD_ADDR 改成 22:22:B7:D4:14:F4、
  关闭 IBS/deep sleep，存为 `/etc/firmware/crnv21_pmos.bin`。
- 桥接层已能伪造 BD_ADDR 为 22:22:B7:D4:14:F4。

### 还没解决的

- 发送 `crbtfw21.tlv` 的 EDL patch 时，芯片不确认（无 VSE ack），
  写入会被流控卡住；说明 Qualcomm EDL 下载流程还缺步骤
  （可能需要先做 baud rate/flow control 配置，或 patch config 命令）。
- DT 缺 bt-reset-gpio/clock，`/dev/btpower` 的 ioctl 只能开稳压器，
  不能释放复位。

### 结论

真正的蓝牙需要：
1. 补 DT 的 qca,bt-reset-gpio 和 clock（需要知道 joan 的 GPIO 号/时钟源）
2. 正确实现/移植 QCA EDL 固件下载（内核 hci_qca+wcn3990 或用户态完整流程）

当前 BT 处于实验状态（可能无 hci0），Wi-Fi 仍缺 PeripheralManager 链。

## 2026-10-26 晚：备份验证 + 主线移植起步

- 新备份 `backup-2026-10-26/` 实测通过：从 fastboot 刷入后 SSH/fbdash/对时/
  根分区扩容全部正常。
- 从运行中的下游系统提取了 **真实设备树**：`/sys/firmware/fdt` →
  `device-tree/joan-downstream.dts`（dtc 反编译，18875 行）。
- 下载了主线 msm8998 fork（6.0，commit 90169e6e）源码。
- 关键发现：主线 `msm8998-mtp.dts` 与 joan 高度接近，已含：
  - `qcom,wcn3990-bt`（blsp1_uart3）
  - `&wifi` 四路 PM8998 稳压器
  - UFS、USB3/DWC3、PM8998/PMI8998
- 下游 joan 的板级标识：`qcom,msm-id = <0x124 0x20001>`、
  `qcom,board-id = <0xc08 0x0>`；已据此生成
  `device-tree/joan-mainline/msm8998-lge-joan.dts`（mtp 基础上改板级标识）。
- 待办：补齐 joan reserved-memory（与上游默认不同）、加进 Makefile、
  用 pmOS 主线包编译、无显示启动测试 WiFi/蓝牙。

## 2026-10-26 深夜：主线移植第一次尝试

- 备份 `backup-2026-10-26` 实测通过（从 fastboot 刷入可用）。
- 从 `/sys/firmware/fdt` 提取下游真实 DT → `device-tree/joan-downstream.dts`。
- 下载 msm8998-mainline 6.0 fork 源码，写 `msm8998-lge-joan.dts`
  （基于 `msm8998-mtp.dts`，改 board-id/msm-id，加 simplefb）。
- 新建 pmOS 包 `linux-lg-joan-mainline`（`device/downstream/`）：
  - 配置打开 `ATH10K=y`、`ATH10K_SNOC=y`、`BT_HCIUART=y`、`SERIAL_MSM=y`、
    `FB_SIMPLE=y`、`CFG80211/MAC80211=y`
  - 编译出 6.0 内核 + 68KB joan DTB，打包成 boot.img（下游 ramdisk）
- **结果：刷入后 LG logo 反复重启**，没有 framebuffer 控制台输出，
  说明内核在 fbcon 之前就挂了，或者 LK 没接受这个 boot image。
- 想用 kexec 绕过 LK 抓日志，但 LG 4.4 内核**没有 CONFIG_KEXEC 符号**
  （配置里写 `CONFIG_KEXEC=y` 会被丢弃），kexec_load 返回 ENOSYS。

### 待办

1. 加 ramoops/pstore 到主线 DT（和下游 DT），抓 panic；
   或找到 joan 的调试 UART。
2. 确认 LK 是否接受该 boot image：可用 msm8998-mainline 自带的
   OnePlus 5 DTB（改成 joan 的 board-id）交叉验证。
3. 主线 DTS 还要补 joan 的 reserved-memory/regulator 差异。

## 2026-10-26 23:10：主线启动失败的定位实验

- 对照组：**下游内核 + 下游 DTB**，用同一套 mkboot 流程构造 → **能启动**，
  证明镜像格式、DTB 追加、LK 都正常。
- **主线内核 + 下游 DTB**、主线 + 主线 DTB、压缩/未压缩 Image、
  `maxcpus=1 nokaslr`、`text_offset=0x80000` 全部仍然 LG logo 重启。
- 给下游/主线 DT 都加了 ramoops（0x9ff00000），下游能注册 pstore
  （`pstore: Registered ramoops as persistent store backend`），
  但主线崩溃后 pstore 里**没有任何记录** → 主线在 pstore 初始化（约 0.4s）之前就挂了，
  甚至早于 fbcon，所以屏幕和 pstore 都抓不到。
- kexec 方案不可行：LG 4.4 内核源码里没有 CONFIG_KEXEC 符号，
  配置写了也会被 Kconfig 丢弃，`kexec_load` 返回 ENOSYS。

### 结论/下一步

主线 6.0 在 joan 上极早期崩溃（<0.4s），需要**真正的早期控制台**才能继续：
1. 找 joan 的调试 UART 测试点（硬件）
2. 或让内核把 earlycon 输出到别的可访问接口（暂时无解）
3. 向 msm8998-mainline 社区确认 LG V30 是否有已知启动问题
4. 尝试其他内核版本（5.x）或不同 Image 头参数

## 补充：misc 分区无 LK 日志

- `misc` 只有 `bootonce-bootloader`、`LinuxLoader` 等字符串，没有启动失败记录。
- msm8998-mainline 仓库没有 joan/LG 相关 issue。

结论：主线在 <0.4s 极早期崩溃，无 fbcon、无 pstore、无 LK 日志；
下一步必须拿到**早期串口**（硬件测试点）或向社区确认 LG V30 的已知问题。

## 2026-10-26 23:25：主线早期崩溃的更多实验（全部失败）

- 对照组（下游 4.4 内核 + 下游 DTB，同一 mkboot 流程）**能启动**。
- 主线 6.0 + 下游 DTB / 主线 DTB、gzip 与未压缩 Image、
  `maxcpus=1 nokaslr`、`text_offset=0x80000`（gzip 与未压缩都试过）、
  去掉 `console=ttyMSM0`、`VA_BITS=39/48`、ramoops/pstore —— **全部 LG logo 重启**。
- pstore 在下游已确认可用，但主线崩溃后无任何记录 → 主线在 0.4s 前挂掉。
- misc/logfs 无 LK 日志；msm8998-mainline 仓库无 joan/LG issue。

### 结论

需要**串口/早期控制台**才能继续；否则只能盲试。
下一步：向 msm8998-mainline 提 issue（已起草 `mainline/issue-for-msm8998.md`），
或找 joan 的 UART 测试点。
