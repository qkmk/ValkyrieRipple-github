# -*- coding: utf-8 -*-
"""
按键采集校准工具 (一次性用)
============================
运行后, 请把这些区域的键**每个按一下** (顺序随意):
  1. 小键盘全部 (0-9, . / * - + Enter, Num Lock)
  2. 方向键 上下左右
  3. Insert/Delete/Home/End/Page Up/Page Down
  4. 左右 Ctrl / Alt / Shift / Win / Fn
  5. 主键区随便按几个 (a, 5, 空格) 作对照
按完后, 在此终端按 Ctrl+C 停止, 它会打印一张表。
不会控制灯, 只是记录按键信息。

管理员提示: 若某些键没被记录到, 请用管理员身份重开终端再运行。
"""
import keyboard
import time

seen = {}   # (name, is_keypad, scan_code) -> 次数

def on_key(e):
    if e.event_type != 'down':
        return
    k = (e.name, bool(e.is_keypad), e.scan_code)
    seen[k] = seen.get(k, 0) + 1
    kp = 'KEYPAD' if e.is_keypad else '      '
    print(f'  按下: name={str(e.name):16s} scan={e.scan_code:6d}  {kp}')

print(__doc__)
print('开始采集... (Ctrl+C 停止)\n')
keyboard.hook(on_key)
try:
    while True:
        time.sleep(0.2)
except KeyboardInterrupt:
    pass
finally:
    keyboard.unhook_all()
    print('\n\n================ 采集结果汇总 ================')
    print(f'{"name":18s}{"is_keypad":11s}{"scan_code"}')
    print('-'*45)
    for (name, kp, sc) in sorted(seen.keys(), key=lambda x: (x[1], x[2])):
        print(f'{str(name):18s}{str(kp):11s}{sc}')
    print('=============================================')
    print(f'共采集到 {len(seen)} 个不同按键。')
