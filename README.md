# Valkyrie Ripple ⌨️🌊

为 **Valkyrie VK99** 机械键盘打造的**按键涟漪光效**程序。

按下任意键，就会从该键位置泛起一圈涟漪，向外扩散并淡出；连续按同一个键可得到
彩虹渐变的涟漪。不按键时键盘保持全黑。

**自带 HID 驱动，直接驱动键盘，无需 OpenRGB 或任何后台服务。**

![涟漪图标](ripple.ico)

---

## ✨ 特性

- **按键触发**：真正的 reactive 光效，涟漪从你按下的那个键荡开（OpenRGB 及其
  Effects 插件都做不到按键触发）。
- **两种配色**：`cycle` 彩虹循环（连按同键色相渐变）/ `random` 随机色。
- **自带驱动**：内置从 OpenRGB 移植的 VK99 HID 协议，用 `hidapi` 直接发送灯光数据，
  **不依赖 OpenRGB / SDK server**。
- **参数热加载**：所有参数在 `config.json`，改完保存**即时生效**，无需重启。
- **防过曝混合**：多个涟漪叠加用透明合成（over），快速打字交叠处也不会冲成纯白。
- **长按过滤**：长按只触发一次涟漪，忽略操作系统的自动重复信号。
- **精确键位映射**：全键盘 102 键位置逐灯校准，含小键盘、方向键、导航键的正确定位。
- **极低占用**：实测 CPU ~0.5%、内存 ~15MB。

---

## 🚀 快速开始

### 方式一：直接运行源码

```bash
pip install -r requirements.txt
python key_ripple.py
```

打字即有涟漪。按 `Ctrl+C` 退出。

> ⚠️ **管理员权限**：若希望在任务管理器、游戏等高权限窗口聚焦时涟漪仍生效，
> 需以管理员身份运行终端（Windows UIPI 机制所致）。

### 方式二：打包成 exe

```bash
pip install pyinstaller
pyinstaller --onefile --noconsole --uac-admin ^
    --icon ripple.ico --name ValkyrieRipple ^
    --add-data "vk99_layout.json;." ^
    --hidden-import hid --hidden-import keyboard ^
    key_ripple.py
```

产物：`dist/ValkyrieRipple.exe`（单文件、无控制台、自动请求管理员权限、带图标）。
把 `config.json` 放在 exe 同目录即可。

---

## ⚙️ 参数说明（config.json）

首次运行会自动生成 `config.json`，每个参数上方都有 `_` 开头的中文说明字段
（程序加载时自动忽略这些说明键）。核心参数：

| 参数 | 含义 |
|---|---|
| `FPS` | 刷新帧率，越高越顺滑越吃 CPU（建议 30~60） |
| `RIPPLE_SPEED` | 涟漪扩散速度（格/秒），越大荡开越快 |
| `RIPPLE_WIDTH` | 涟漪光环厚度（格），越大越粗越柔 |
| `RIPPLE_LIFE` | 单个涟漪存活时间（秒），越大拖尾越久 |
| `COL_ASPECT` | 横向拉伸补偿（键盘扁，让涟漪更圆），1=不补偿 |
| `MAX_RIPPLES` | 最多同时存在的涟漪数，防狂敲卡顿 |
| `BRIGHTNESS` | 整体亮度 0.0~1.0 |
| `SATURATION` | 颜色饱和度 0.0（发白）~1.0（最鲜艳） |
| `COLOR_MODE` | `cycle`=连按同键彩虹渐变 / `random`=每次随机色 |
| `HUE_STEP` | 仅 cycle：每次按键色相前进量 0~1（0.05 约 20 键转一圈） |
| `BLEND_MODE` | 涟漪叠加：`over`（推荐，不过曝）/ `max`（较柔）/ `add`（易过曝） |

改完保存，运行中的程序会自动重载（终端打印 `[配置已重载]`）。

---

## 📁 文件说明

| 文件 | 作用 |
|---|---|
| `key_ripple.py` | 主程序：按键监听、涟漪渲染、配置热加载 |
| `valkyrie_driver.py` | 自写 VK99 HID 驱动（协议移植自 OpenRGB） |
| `vk99_layout.json` | 键盘布局数据（LED 顺序、矩阵坐标、键名） |
| `config.example.json` | 参数示例（含说明），首次运行会据此生成 config.json |
| `ripple.ico` | 程序图标 |
| `tools_capture_keys.py` | 工具：采集按键的 scan_code / is_keypad（换键盘/排错用） |

---

## 🔧 换成别的键盘？

本程序针对 Valkyrie VK99 的布局和 HID 协议。若要移植到其它键盘：

1. `valkyrie_driver.py` 里的键码表和发送协议需换成目标键盘的（可参考 OpenRGB
   对应型号的 `Controllers/` 源码）。
2. `vk99_layout.json` 需换成目标键盘的 LED 布局。
3. `key_ripple.py` 里 `build_key_map` 的按键→LED 映射需按目标键盘重新校准
   （用 `tools_capture_keys.py` 采集按键，逐灯点亮确认位置）。

---

## 📜 许可

**GPL-2.0-or-later**。本项目的 HID 通信协议移植自 [OpenRGB](https://gitlab.com/CalcProgrammer1/OpenRGB)
的 `ValkyrieKeyboardController`（GPL-2.0），详见 [LICENSE](LICENSE)。
