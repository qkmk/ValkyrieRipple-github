# -*- coding: utf-8 -*-
"""
Valkyrie VK99 独立 HID 驱动
===========================
不依赖 OpenRGB, 用 hidapi 直接把颜色发到键盘。
协议翻译自 OpenRGB 源码 ValkyrieKeyboardController (GPL-2.0)。

用法:
    drv = ValkyrieDriver()
    drv.open()
    drv.send_colors(colors)   # colors: 长度102的list, 每个是(r,g,b) 0~255
    drv.close()
"""
import time
import hid

VID = 0x05AC
PID = 0x024F

# 102键版键码表 (照抄 OpenRGB 源码 key_code_103), 顺序 = LED 0..101
KEY_CODE_103 = [
    0x01,0x02,0x03,0x04,0x05,0x06,0x07,0x08,0x09,0x0A,0x0B,0x0C,0x0D,0x77,0x70,0x73,
    0x75,0x78,0x13,0x14,0x15,0x16,0x17,0x18,0x19,0x1A,0x1B,0x1C,0x1D,0x1E,0x1F,0x67,
    0x74,0x20,0x21,0x22,0x7A,0x25,0x26,0x27,0x28,0x29,0x2A,0x2B,0x2C,0x2D,0x2E,0x2F,
    0x30,0x31,0x43,0x76,0x32,0x33,0x34,0x7B,0x37,0x38,0x39,0x3A,0x3B,0x3C,0x3D,0x3E,
    0x3F,0x40,0x41,0x42,0x55,0x79,0x44,0x45,0x46,0x49,0x4A,0x4B,0x4C,0x4D,0x4E,0x4F,
    0x50,0x51,0x52,0x53,0x54,0x65,0x56,0x57,0x58,0x6A,0x5B,0x5C,0x5D,0x5E,0x5F,0x60,
    0x62,0x63,0x64,0x66,0x68,0x69,
]
N_LEDS = 102


class ValkyrieDriver:
    def __init__(self):
        self.dev = None

    def open(self):
        """打开 VK99 的灯控接口 (MI_02, usage_page=0xff13)。"""
        target = None
        for d in hid.enumerate(VID, PID):
            path = d["path"].decode("ascii", "ignore").lower() if isinstance(d["path"], bytes) else str(d["path"]).lower()
            # 灯控接口特征: 接口2 (mi_02) 且厂商自定义 usage_page 0xff13
            if "mi_02" in path and d.get("usage_page", 0) == 0xff13:
                target = d["path"]
                break
        if target is None:
            # 退回: 只按 mi_02 匹配
            for d in hid.enumerate(VID, PID):
                path = d["path"].decode("ascii", "ignore").lower() if isinstance(d["path"], bytes) else str(d["path"]).lower()
                if "mi_02" in path:
                    target = d["path"]
                    break
        if target is None:
            raise RuntimeError("找不到 VK99 灯控接口 (MI_02)。键盘没插好, 或被 OpenRGB 占用?")
        self.dev = hid.device()
        self.dev.open_path(target)

    def _feature(self, buf65):
        """发一个 65 字节 feature report (buf65[0]=report id=0)。"""
        self.dev.send_feature_report(bytes(buf65))

    def _init_packet(self):
        buf = [0x00] * 65
        buf[1] = 0x04
        buf[2] = 0x20
        buf[9] = 0x08
        self._feature(buf)
        time.sleep(0.001)
        try:
            self.dev.get_feature_report(0, 65)
        except Exception:
            pass
        time.sleep(0.001)

    def _terminate_packet(self):
        buf = [0x00] * 65
        self._feature(buf)          # 先发全0
        time.sleep(0.001)
        buf = [0x00] * 65
        buf[1] = 0x04
        buf[2] = 0x02
        self._feature(buf)
        time.sleep(0.001)
        try:
            self.dev.get_feature_report(0, 65)
        except Exception:
            pass
        time.sleep(0.001)

    def send_colors(self, colors):
        """colors: 长度102的list, 每个 (r,g,b) 0~255。顺序 = LED 0..101。"""
        # 组装 [键码,R,G,B] x 102  (对应源码 usb_buf_normal, 每键4字节)
        payload = bytearray(N_LEDS * 4)
        for i in range(N_LEDS):
            r, g, b = colors[i]
            payload[i * 4]     = KEY_CODE_103[i]
            payload[i * 4 + 1] = r & 0xFF
            payload[i * 4 + 2] = g & 0xFF
            payload[i * 4 + 3] = b & 0xFF

        self._init_packet()
        # 分7批发送: i=0..6, 每批16键(最后一批6键)
        for i in range(7):
            data_num = 16 if i < 6 else (N_LEDS - 16 * 6)   # 最后一批 = 102-96 = 6
            send = [0x00] * 65
            for index in range(data_num):
                src = index * 4 + i * 64
                send[index * 4 + 1] = payload[src]
                send[index * 4 + 2] = payload[src + 1]
                send[index * 4 + 3] = payload[src + 2]
                send[index * 4 + 4] = payload[src + 3]
            self._feature(send)
            time.sleep(0.001)
        self._terminate_packet()

    def close(self):
        if self.dev:
            try:
                self.dev.close()
            except Exception:
                pass
            self.dev = None


if __name__ == "__main__":
    # 自测: 全键盘点亮红, 再绿, 再灭
    import sys
    drv = ValkyrieDriver()
    try:
        drv.open()
    except Exception as e:
        print("打开失败:", e)
        print("提示: 若 OpenRGB 正开着占用键盘, 请先完全退出 OpenRGB。")
        sys.exit(1)
    print("驱动已打开。全键盘 -> 红(2秒) -> 绿(2秒) -> 灭")
    drv.send_colors([(255, 0, 0)] * N_LEDS); time.sleep(2)
    drv.send_colors([(0, 255, 0)] * N_LEDS); time.sleep(2)
    drv.send_colors([(0, 0, 0)] * N_LEDS)
    drv.close()
    print("完成。若键盘刚才变红再变绿 -> 自写驱动成功!")
