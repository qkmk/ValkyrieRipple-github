# -*- coding: utf-8 -*-
"""
Valkyrie VK99 - 按键涟漪光效 (Key Ripple)  [独立版, 不依赖 OpenRGB]
==================================================================
按下任意键 -> 从该键位置泛起一圈涟漪, 向外扩散并淡出。不按键时键盘全黑。

- 自带 HID 驱动 (valkyrie_driver.py), 直接控制键盘, 无需 OpenRGB / SDK server。
- 所有参数在同目录 config.json 里, 改完保存即时生效 (热加载, 无需重启)。

依赖: hidapi, keyboard        运行: python key_ripple.py
停止: 终端 Ctrl+C, 或按键盘 ESC。
"""

import os
import sys
import json
import time
import math
import random
import colorsys

import keyboard
from valkyrie_driver import ValkyrieDriver, N_LEDS

# 资源目录: 兼容 PyInstaller 打包 (sys._MEIPASS) 与源码运行
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
    BUNDLE_DIR = getattr(sys, "_MEIPASS", BASE_DIR)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    BUNDLE_DIR = BASE_DIR

CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
LAYOUT_PATH = os.path.join(BUNDLE_DIR, "vk99_layout.json")

# 默认参数 (config.json 缺失时用这些, 并自动生成一份)
DEFAULT_CONFIG = {
    "FPS": 60,               # 刷新帧率
    "RIPPLE_SPEED": 12.0,    # 涟漪扩散速度 (格/秒)
    "RIPPLE_WIDTH": 1.5,     # 涟漪光环厚度 (格)
    "RIPPLE_LIFE": 1.5,      # 单个涟漪存活时间 (秒)
    "COL_ASPECT": 1.8,       # 列方向拉伸补偿 (键盘扁, 让涟漪更圆); 1=不补偿
    "MAX_RIPPLES": 40,       # 最多同时存在的涟漪数
    "BRIGHTNESS": 1.0,       # 整体亮度 0.0~1.0
    "SATURATION": 0.9,       # 颜色饱和度 0.0(发白)~1.0(鲜艳)
    "COLOR_MODE": "cycle",   # "cycle"=彩虹循环 / "random"=随机色
    "HUE_STEP": 0.05,        # cycle 模式每次按键色相前进量 (0~1)
    "BLEND_MODE": "over",    # "over"(推荐)/"max"/"add"
}

# 参数说明 (会写进 config.json 的 "_说明" 字段, 方便调参; 程序加载时忽略 _ 开头的键)
CONFIG_HELP = {
    "_说明": "改完保存即时生效(无需重启)。下面每个参数的含义:",
    "_FPS": "刷新帧率, 越高越顺滑越吃CPU (建议30~60)",
    "_RIPPLE_SPEED": "涟漪扩散速度(格/秒), 越大荡开越快",
    "_RIPPLE_WIDTH": "涟漪光环厚度(格), 越大光环越粗越柔",
    "_RIPPLE_LIFE": "单个涟漪存活时间(秒), 越大拖尾越久",
    "_COL_ASPECT": "横向拉伸补偿(键盘扁,让涟漪更圆); 1=不补偿, 常用1.8~2.0",
    "_MAX_RIPPLES": "最多同时存在的涟漪数, 防狂敲卡顿",
    "_BRIGHTNESS": "整体亮度 0.0~1.0",
    "_SATURATION": "颜色饱和度 0.0(发白)~1.0(最鲜艳)",
    "_COLOR_MODE": "配色: cycle=连按同键彩虹渐变 / random=每次随机色",
    "_HUE_STEP": "仅cycle模式: 每次按键色相前进量0~1, 越大转色越快(0.05约20键一圈)",
    "_BLEND_MODE": "涟漪叠加: over(推荐,不过曝) / max(较柔) / add(易过曝变白)",
}


def _write_default_config():
    """写一份带说明的默认 config.json (说明字段在前, 参数在后)。"""
    out = dict(CONFIG_HELP)
    out.update(DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def load_config():
    """读取 config.json; 缺失或损坏则用默认值并回写。忽略 _ 开头的说明键。返回 dict。"""
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            user = json.load(f)
        cfg = dict(DEFAULT_CONFIG)
        # 只取已知参数, 忽略 "_说明"/"_FPS" 等注释键
        cfg.update({k: user[k] for k in user
                    if k in DEFAULT_CONFIG and not k.startswith("_")})
        return cfg
    except Exception:
        _write_default_config()
        return dict(DEFAULT_CONFIG)


def build_key_map(layout):
    """用布局数据(dict, 来自 vk99_layout.json)建立按键->(行,列)映射。

    定位优先级: (is_keypad, scan_code) 硬件级 > 名字兜底。
    返回 (kp_map, name_map, led_pos)。
    """
    mm = layout["matrix_map"]           # 二维list, 值=LED索引或null
    led_names = layout["led_names"]

    # LED索引 -> (行,列)
    led_pos = {}
    for r, row in enumerate(mm):
        for col, v in enumerate(row):
            if v is not None:
                led_pos[v] = (r, col)

    # 坐标修正: PageUp(LED51)/PageDown(LED69) 物理在第一行 End 右侧, 但 OpenRGB
    # 矩阵把它们排到中右部。改成紧接 End 右侧, 使涟漪圆心在右上角。
    COORD_OVERRIDE = {51: (0, 22), 69: (0, 23)}
    for led_i, pos in COORD_OVERRIDE.items():
        if led_i in led_pos:
            led_pos[led_i] = pos

    def P(org_name):
        """按 LED 名字(如 'a'/'escape')取坐标。"""
        for i, nm in enumerate(led_names):
            if i in led_pos and nm.replace("Key:", "").strip().lower() == org_name:
                return led_pos[i]
        return None

    # (is_keypad, scan_code) -> 坐标。值: 名字(str) / ("led",idx) / (行,列)
    KP = {
        # 小键盘 (is_keypad=True)
        (True, 69): "num lock",
        (True, 53): "number pad /",
        (True, 55): "number pad *",
        (True, 74): "number pad -",
        (True, 78): "number pad +",
        (True, 28): "number pad enter",
        (True, 82): "number pad 0",
        (True, 83): "number pad .",
        (True, 71): "number pad 7",
        (True, 72): "number pad 8",
        (True, 73): "number pad 9",
        (True, 75): "number pad 4",
        (True, 76): "number pad 5",
        (True, 77): "number pad 6",
        (True, 79): "number pad 1",
        (True, 80): "number pad 2",
        (True, 81): "number pad 3",
        # 方向键 (is_keypad=False)
        (False, 72): "up arrow",
        (False, 80): "down arrow",
        (False, 75): "left arrow",
        (False, 77): "right arrow",
        # 右上角四导航键: 实测 LED 索引 Home=16/End=17/PgUp=51/PgDn=69
        (False, 71): ("led", 16),
        (False, 79): ("led", 17),
        (False, 73): ("led", 51),
        (False, 81): ("led", 69),
        # 主键区独立 Delete 键 (第一行 F12 右边): LED13, 坐标(0,17)。
        # is_keypad=False 区别于小键盘 Del(True,83)。
        (False, 83): ("led", 13),
    }
    kp_map = {}
    for key, org in KP.items():
        if isinstance(org, tuple) and len(org) == 2 and org[0] == "led":
            pos = led_pos.get(org[1])
        elif isinstance(org, tuple):
            pos = org
        else:
            pos = P(org)
        if pos is not None:
            kp_map[key] = pos

    # 名字兜底 (字母/数字/符号/修饰键)
    alias = {
        "esc": "escape", "escape": "escape",
        "space": "space", "spacebar": "space",
        "enter": "enter", "return": "enter",
        "backspace": "backspace",
        "tab": "tab", "caps lock": "caps lock",
        "shift": "left shift", "left shift": "left shift", "right shift": "right shift",
        "ctrl": "left control", "left ctrl": "left control", "right ctrl": "right control",
        "alt": "left alt", "left alt": "left alt", "right alt": "right alt",
        "windows": "left windows", "left windows": "left windows",
        "right fn": "right fn", "fn": "right fn",
        "print screen": "print screen", "pause": "pause/break",
        "-": "-", "=": "+", "+": "+",
        "[": "[", "]": "]", "\\": "\\", ";": ";", "'": "'",
        ",": ",", ".": ".", "/": "/", "`": "`",
    }
    for k in "abcdefghijklmnopqrstuvwxyz0123456789":
        alias[k] = k
    for i in range(1, 13):
        alias["f%d" % i] = "f%d" % i

    name_map = {}
    for kbd_name, org_name in alias.items():
        pos = P(org_name)
        if pos is not None:
            name_map[kbd_name] = pos

    return kp_map, name_map, led_pos


def main():
    # 加载布局
    try:
        with open(LAYOUT_PATH, "r", encoding="utf-8") as f:
            layout = json.load(f)
    except Exception as e:
        print("[错误] 读不到布局文件 %s: %s" % (LAYOUT_PATH, e))
        sys.exit(1)

    # 打开自写 HID 驱动
    drv = ValkyrieDriver()
    try:
        drv.open()
    except Exception as e:
        print("[错误] 打开键盘失败: %s" % e)
        print("       如果 OpenRGB 正开着占用键盘, 请先完全退出 OpenRGB。")
        sys.exit(1)

    kp_map, name_map, led_pos = build_key_map(layout)
    n_leds = layout["n_leds"]

    # 加载参数 + 记录 config 文件修改时间 (用于热加载)
    cfg = load_config()
    try:
        cfg_mtime = os.path.getmtime(CONFIG_PATH)
    except Exception:
        cfg_mtime = 0

    print("已启动 (独立驱动): %s (%d 键)" % (layout.get("name", "VK99"), n_leds))
    print("参数文件: %s  (改完保存即时生效)" % CONFIG_PATH)
    print("-> 敲键盘泛起涟漪。Ctrl+C 或 ESC 退出。")

    ripples = []
    hue_cursor = [0.0]
    held = set()

    def on_key(event):
        name = (event.name or "").lower()
        if event.event_type == "up":
            held.discard(event.scan_code)
            return
        if event.event_type != "down":
            return
        # 长按过滤: 自动重复信号忽略
        if event.scan_code in held:
            return
        held.add(event.scan_code)

        pos = kp_map.get((bool(event.is_keypad), event.scan_code))
        if pos is None:
            pos = name_map.get(name)
        if pos is None:
            return
        if cfg["COLOR_MODE"] == "cycle":
            hue = hue_cursor[0]
            hue_cursor[0] = (hue_cursor[0] + cfg["HUE_STEP"]) % 1.0
        else:
            hue = random.random()
        if len(ripples) >= cfg["MAX_RIPPLES"]:
            ripples.pop(0)
        ripples.append({"r": pos[0], "c": pos[1], "hue": hue,
                        "t0": time.monotonic()})

    keyboard.hook(on_key)

    last_cfg_check = 0.0

    try:
        while True:
            now = time.monotonic()

            # 热加载: 每 ~0.5s 检查 config.json 是否被改动
            if now - last_cfg_check > 0.5:
                last_cfg_check = now
                try:
                    m = os.path.getmtime(CONFIG_PATH)
                    if m != cfg_mtime:
                        cfg_mtime = m
                        cfg.update(load_config())
                        print("[配置已重载]")
                except Exception:
                    pass

            speed = cfg["RIPPLE_SPEED"]; width = cfg["RIPPLE_WIDTH"]
            life = cfg["RIPPLE_LIFE"];   aspect = cfg["COL_ASPECT"]
            sat = cfg["SATURATION"];     bright = cfg["BRIGHTNESS"]
            blend = cfg["BLEND_MODE"]

            buf = [[0.0, 0.0, 0.0] for _ in range(n_leds)]

            alive = []
            for rp in ripples:
                if (now - rp["t0"]) <= life:
                    alive.append(rp)
            ripples[:] = alive

            for rp in alive:
                age = now - rp["t0"]
                radius = age * speed
                fade = 1.0 - (age / life)
                cr, cc = rp["r"], rp["c"]
                rr, gg, bb = colorsys.hsv_to_rgb(rp["hue"], sat, 1.0)
                for led_i, (lr, lc) in led_pos.items():
                    dr = lr - cr
                    dc = (lc - cc) / aspect
                    d = abs(math.hypot(dr, dc) - radius)
                    if d >= width:
                        continue
                    a = (1.0 - d / width) * fade
                    if a <= 0:
                        continue
                    px = buf[led_i]
                    if blend == "add":
                        px[0] += rr * a; px[1] += gg * a; px[2] += bb * a
                    elif blend == "max":
                        px[0] = max(px[0], rr * a)
                        px[1] = max(px[1], gg * a)
                        px[2] = max(px[2], bb * a)
                    else:
                        inv = 1.0 - a
                        px[0] = rr * a + px[0] * inv
                        px[1] = gg * a + px[1] * inv
                        px[2] = bb * a + px[2] * inv

            # 转成 (r,g,b) 0~255 元组数组, 发给驱动
            colors = []
            for i in range(n_leds):
                r = min(1.0, buf[i][0]) * bright
                g = min(1.0, buf[i][1]) * bright
                b = min(1.0, buf[i][2]) * bright
                colors.append((int(r * 255), int(g * 255), int(b * 255)))
            drv.send_colors(colors)

            elapsed = time.monotonic() - now
            frame_dt = 1.0 / cfg["FPS"]
            if elapsed < frame_dt:
                time.sleep(frame_dt - elapsed)

    except KeyboardInterrupt:
        pass
    finally:
        try:
            drv.send_colors([(0, 0, 0)] * n_leds)
        except Exception:
            pass
        try:
            drv.close()
        except Exception:
            pass
        keyboard.unhook_all()
        print("\n已退出, 键盘已熄灭。")


if __name__ == "__main__":
    main()
