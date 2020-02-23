from syskaled.syskaled import SyskaLed, RGB, HSV
import time

from somesources import Desktop, AndroidTV


def normalize(rgb):
    """ Adjusted according to ability my LED
    """
    hsv = SyskaLed.rgb_to_hsv(rgb)
    s = int(75 + (hsv.s/4))
    v = int(50 + (hsv.v/2))
    return HSV(hsv.h, s, v)


class RoomThemeDemo:
    INTERVAL = 2  # change every x sec
    DEBUG = True
    def __init__(self, ledargs, src, src_args=()):
        self.led = SyskaLed(*ledargs)
        self.src = src
        self.src_args = src_args
        
    def run(self):
        self.led.on()
        with self.src(*self.src_args) as img_source:
            try:
                while True:
                    colr = img_source.get_theme_color()    
                    #colr = normalize(colr)             
                    r = self.led.set_color(colr)
                    if self.DEBUG:
                        print(f"DEBUG : {colr} : {self.prevcolor} : {diff}")
                    time.sleep(self.INTERVAL)
            except KeyboardInterrupt:
                self.led.set_mode()
                self.led.set_brightness(100)


if __name__ == '__main__':
    ledargs = ('04************fc', '2************1', '192.168.1.106')

    #tvargs = ('192.168.1.100', 'adbkey')
    #from_tv = RoomTheme(ledargs, AndroidTV, tvargs)

    rt = RoomThemeDemo(ledargs, Desktop)
    rt.run()


