# LG V30 (lg-joan) postmarketOS 可启动镜像

本目录是为一台 **LG V30（US998，代号 joan，MSM8998 / 骁龙 835）** 构建并已在真机上验证启动的
postmarketOS edge 镜像。内核基于 LineageOS 的 LG msm8998 下游内核（Linux 4.4.302）。

## 当前状态（已实测）

- ✅ 解锁 bootloader 的 US998 上可正常启动
- ✅ 内核 → initramfs → ext4 根文件系统 → openrc → sshd 全流程通过
- ✅ USB 网络正常：电脑侧 `172.16.42.2`，手机侧 `172.16.42.1`
- ✅ SSH 可登录（用户 `user`，密码 `147147`）
- ✅ **屏幕已点亮**：通过 fbdev + mmap 直接写 `/dev/fb0`，开机自动显示实时仪表盘（时钟、电池、运行时间、USB IP、内核版本）
- ⚠️ 没有 VT/fbcon（开启会导致内核崩溃），也没有 DRM；当前 UI 是自绘的 framebuffer 触摸仪表盘（Xorg/fbdev 仍未跑通）
- ✅ **触摸可用**：`touch_dev`（`/dev/input/event1`，多点触控协议 B）
- ✅ **触摸桌面**：主页 + 终端（pty shell）、屏幕键盘（字母/符号/方向键/Esc/Ctrl）、亮度 ±、重启/关机
- ⚠️ Wi-Fi 暂未工作：qcacld 能加载、HDD 初始化，但没有 wlan0（缺 cnss/WLFW 固件触发）
- ✅ **蓝牙可用**：WCN3990 通过用户态 H4 ↔ `/dev/vhci` 桥接，BlueZ 正常识别、扫描、发现设备（详见 `debug/NOTES.md`）
- 📌 最新进展与明晚计划见 [debug/NOTES.md](debug/NOTES.md)

## 文件说明

| 文件 | 大小 | 用途 |
| --- | --- | --- |
| `boot.img` | 27 MB | Android boot 镜像（`Image.gz-dtb` 内核 + initramfs），刷入 `boot` 分区 |
| `lg-joan.img` | 1.2 GB | ext4 根文件系统（单分区），刷入 `userdata` 分区 |
| `SHA256SUMS` | — | 校验和：`sha256sum -c SHA256SUMS` |
| `flash.sh` | — | 一键校验 + 刷入脚本（二次确认） |
| `backup/` | 1.5 GB | 当前可用系统的完整备份（boot 分区 + 根文件系统快照 + 恢复脚本） |
| `sources/` | — | `device-lg-joan`、`linux-lg-joan` 两个 pmaports 包定义 |

`boot.img` 为 Android boot header v0：页大小 4096，内核地址 `0x8000`、ramdisk `0x01000000`、
tags `0x00000100`，与 LineageOS 对 joan 的 BoardConfig 一致；28 MB < 该机 40 MB 的 boot 分区。

## 刷入

> ⚠️ 会清空 userdata（Android 数据），请先备份。

```bash
sudo pacman -S android-tools       # 已安装可跳过
cd lg-v30-postmarketos
./flash.sh                         # 或手动：
# fastboot flash boot boot.img
# fastboot flash userdata lg-joan.img
# fastboot reboot
```

首次启动约 30 秒（含根文件系统扩容）。

## 备份与恢复

> **注意（2026-10-26 修）**：用 tar 做根文件系统快照时，`/proc /sys /dev /run /tmp /var/log`
> 这些挂载点如果被 `--exclude` 掉，必须**在镜像里补建空目录**（`/tmp` 权限 1777），
> 否则镜像无法启动（initramfs switch_root 后没有 /proc，openrc/sshd 全挂）。


当前可用系统已完整备份到 `backup/`（boot 分区 40MB 转储 + 1.21GB 根文件系统快照，含 SSH host key、屏幕仪表盘等运行时状态），
随时可以刷回：

```bash
cd backup && ./restore.sh
```

详见 [backup/RESTORE.md](backup/RESTORE.md)。

## 屏幕仪表盘（fbdash）

- 显示：`/dev/fb0`，1440×2880，32bpp，**RGBA** 字节序（写错顺序会红蓝互换）；
  内核 fb 的 `write()` 返回 ENODEV，必须用 `mmap` 写入。
- 开机自启：`/etc/local.d/fbdash.start`（openrc 的 local 服务），脚本在 `/usr/local/bin/fbdash.py`。
- 背光：`/sys/class/leds/lcd-backlight{,-ex}/brightness`，上限 511，当前 180（脚本启动时设置）。
- 修改屏幕上的留言：

  ```bash
  echo "hello from SSH" | sudo tee /run/fbdash-message
  sudo rc-service fbdash restart   # 或等 1 秒自动刷新
  ```

- 触摸：`/dev/input/event1`（`touch_dev`），协议 B（ABS_MT_POSITION_X/Y）。
- 桌面：主页【终端】【亮度 -】【亮度 +】【重启】【关机】；
  终端页用 `pty.fork()` 跑 `/bin/sh -i`，屏幕键盘支持字母/数字/符号页、Esc、方向键、Tab、Ctrl、退格、回车。
- 终端里可运行命令（`ls`、`uname -a`、`ip a` 等），方向键可翻命令历史。
- 中文显示需要 CJK 字体，已装 `font-wqy-zenhei`（`/usr/share/fonts/wqy-zenhei/wqy-zenhei.ttc`）。
- 仪表盘只在画面变化时重绘（避免双缓冲撕裂/闪烁）；源码在 `/usr/local/bin/fbdash.py`。
- **电源键**（`/dev/input/event0`，`qpnp_pon`，KEY_POWER=116）：短按熄屏/亮屏。
  熄屏 = 背光写 0 + `FBIOBLANK` 关屏；亮屏恢复原背光并强制整屏重绘。
- **30 秒无操作自动熄屏**（触摸或电源键都会重置计时）。
- 主页信息：电池、内存（已用/总量）、CPU 占用（2 秒采样）、存储（已用/总量）、运行时间、IP、背光。
- 开机自动对时：`/etc/local.d/timesync.start` → `/usr/local/bin/timesync.sh`，
  等 USB 网络有外网后 `ntpd -q` 校时（最多重试 1 小时），用到 aliyun NTP 与 pool.ntp.org。

### 调整仪表盘

改 `/usr/local/bin/fbdash.py`，然后重启：

```bash
python3 -m py_compile /usr/local/bin/fbdash.py   # 先查语法（有错会打印行号）
sudo /etc/local.d/fbdash.start                   # 会先查语法，再 pkill 旧实例并启动
tail -f /var/log/fbdash.log                      # 看日志/报错
```

> `/etc/local.d/fbdash.start` 现在会先做语法检查；**语法错误时不会杀掉正在运行的实例**，
> 避免改错一行就黑屏。错误详情在 `/tmp/fbdash-syntax.log`。

常用改动点（都在文件顶部/对应函数里）：

| 想改什么 | 位置 |
| --- | --- |
| 自动熄屏时间 | `main()` 里 `time.time() - state["last"] > 30` |
| 默认亮度 | `main()` 里 `set_bright(180)`；范围 30~511 |
| 主页标题/字号/颜色 | `render_home()`：`f_title`/`f_clock`/`f_info`、`fill=(r,g,b,255)` |
| 主页信息行 | `render_home()` 的 `rows = [("电池", battery()), ("内存", ...), ("CPU", ...), ("存储", ...), ...]`；数据函数在 `mem_info()`/`disk_info()`/`cpu_reader()` |
| 主页按钮 | `home_buttons()` 返回 `(x0,y0,x1,y1,文字,动作)`；动作在 `tap()` 里处理。`bt` 会调用 `/usr/local/bin/btconnect.sh`（开蓝牙→连已配对设备或设为可被发现） |
| 终端字体/行高/列数 | `render_term()` 的 `f_term`、`line_h`、`ln[:64]` |
| 键盘按键 | `kb_rows()`：每项 `(显示文字, 发送的 code)`；特殊 code 在 `key_press()` 里分支。`Shift` 一次性大写/符号、`Caps` 大写锁定（`state["shift"]/state["caps"]`） |
| 键盘位置/大小 | `KEY_W`、`KEY_H`、`GAP`、`KB_Y0` |
| 颜色主题 | `render_home()`/`render_term()` 里的 `fill=` 元组 |

新增主页按钮示例：在 `home_buttons()` 里加
`(90, 2640, 390, 2800, "我的应用", "myapp")`，并在 `tap()` 里加
`elif action == "myapp": os.system("...")`。

## 登录

```bash
# 手机用 USB 连接电脑，等待 usb0/网卡出现（约 172.16.42.2）
ssh user@172.16.42.1              # 密码 147147
```

登录后建议：

```bash
passwd                            # 修改密码
sudo apk update && sudo apk upgrade
```

## 回滚到 LineageOS

```bash
fastboot flash boot <LineageOS 的 boot.img>
```

LineageOS 官方 joan 构建（22.2 nightly）仍可下载，zip 内的 `boot.img` 可直接用于恢复：
<https://download.lineageos.org/devices/joan>

## 本镜像相对原始构建做的修复

原始 `pmbootstrap install` 产物在 openrc 下有几个问题，已在镜像中修正：

1. **sshd 无法启动**：openrc 的 `/etc/init.d/sshd` 调用 `/usr/sbin/sshd`，而安装的
   `openssh-server-pam` 只提供 `sshd.pam`。已在镜像中补上可执行文件 `/usr/bin/sshd`。
2. **启动卡在 `udev-settle`**：该机充电器 IRQ 持续产生 uevent，`udevadm settle` 永远等不到队列清空，
   导致 openrc sysinit 卡死。已从 sysinit 运行级移除 `udev-settle`。
3. **splash/plymouth 参数**：已从内核 cmdline 去掉 `splash plymouth.*`，避免无 DRM/VT 环境下的额外风险。
4. **VT/fbcon**：开启后内核会在启动早期崩溃（LG mdss fb 与 fbcon 不兼容），因此关闭 `CONFIG_VT`，
   仅保留串口 `ttyMSM0` 控制台；屏幕显示停留在启动 logo。

重新构建时如需复现，可在 `pmbootstrap install` 后对镜像执行：

```bash
# 1) sshd 可执行文件
debugfs -R "dump /usr/bin/sshd.pam /tmp/sshd.bin" lg-joan.img
debugfs -w -R "write /tmp/sshd.bin /usr/bin/sshd" lg-joan.img
debugfs -w -R "sif /usr/bin/sshd mode 0100755" lg-joan.img
# 2) 去掉 udev-settle
debugfs -w -R "rm /etc/runlevels/sysinit/udev-settle" lg-joan.img
```

## 重新构建

```bash
pmbootstrap -p ~/pmaports-joan -j $(nproc) build --arch aarch64 --lax linux-lg-joan
pmbootstrap -p ~/pmaports-joan -j $(nproc) install --single-partition --password 147147
pmbootstrap -p ~/pmaports-joan export
```

## 2026-10-23 凌晨更新

- 修正了 boot 镜像打包：之前 ramdisk 偏移取错，导致所有重打包镜像启动失败；
  正确方法已封装成 `tools/mkboot.sh`（配套 `tools/ramdisk-real.gz`、`tools/cmdline.txt`）
- ✅ 蓝牙已打通：用户态 `bth4vhci.py` 把 `/dev/ttyHS0` 的 H4 包桥接到 `/dev/vhci`，
  `btwait.py` 等芯片上电、`/etc/local.d/bt.start` 开机自启；重启后能扫描到设备
- Wi-Fi：r3 内核（`QCA_CLD_WLAN=m`）`modprobe wlan` 成功、HDD 初始化，
  但 icnss 的 WLFW QMI 计数器为 0，需要 cnss/WLFW 触发固件加载
- 内核包矩阵（r1/r3/r5/r7/r15/r17）、恢复方法和明晚顺序见 [debug/NOTES.md](debug/NOTES.md)

## 后续可做

- 蓝牙：可选优化——给芯片写入正确的 BD address（当前是 00:00:00:00:5A:AD）、
  配对/连接实际设备验证
- Wi-Fi：实现最小 cnss/WLFW QMI 触发，或移植 cnss-daemon
- 用 `tools/mkboot.sh` 重新验证 panic 画屏内核（r15）
- 触摸校准、电池/充电状态确认

## 参考

- LineageOS 设备树：<https://github.com/LineageOS/android_device_lge_joan>
- LineageOS 内核：<https://github.com/LineageOS/android_kernel_lge_msm8998>
- postmarketOS 移植文档：<https://postmarketos.org/porting/>
- 下游内核说明：<https://wiki.postmarketos.org/wiki/Downstream_kernel_specific_package>
