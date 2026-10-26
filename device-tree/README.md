# Device tree work for the LG V30 (joan)

## Files

- `joan-downstream.dts` — the **running downstream DT**, decompiled from
  `/sys/firmware/fdt` (`dtc -I dtb -O dts`). Use this as the reference for
  joan-specific values (regulators, reserved memory, GPIOs, panel).
- `joan-mainline/msm8998-lge-joan.dts` — **work in progress** for mainline.
  Based on mainline `msm8998-mtp.dts`, which already contains:
  - `bluetooth { compatible = "qcom,wcn3990-bt"; }` on `blsp1_uart3`
  - `&wifi` with `vdd-0.8-cx-mx/l7a/l17a/l25a` supplies
  - UFS, USB3/DWC3, PM8998/PMI8998 regulators

  Changed so far: board id / msm-id / model to match joan so LK selects it.
  TODO: reserved-memory regions (joan differs from upstream defaults),
  display/panel (optional for headless bring-up), touch.

## Board identification (from downstream DT)

```
qcom,msm-id   = <0x124 0x20001>;   /* 292, v2.1 */
qcom,board-id = <0xc08 0x0>;
```

## Mainline references

- Kernel fork: https://gitlab.com/msm8998-mainline/linux (6.0)
- pmOS package: `linux-postmarketos-qcom-msm8998`
- WiFi/BT proven on OnePlus 5 (same MSM8998 + WCN3990)
