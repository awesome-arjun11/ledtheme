from adb_shell.adb_device import AdbDeviceTcp
from adb_shell.auth.sign_pythonrsa import PythonRSASigner
from imgsource import ImageSourceBase
from io import BytesIO
from PIL import Image, ImageGrab

class AndroidTV(ImageSourceBase):
    """ Works via ADB requires USB debugging enabled and require adbkey file for authentication (generate new and copy files to device
    or use old ones usually found at [~/.android/adbkey, %HOMEDRIVE%%HOMEPATH%\.android\adbkey]
    Works with all android based TVs
    """

    def __init__(self, ip, adbkeypath='adbkey', port=5555):
        self.signer = self._get_signer(adbkeypath)
        self.ip = ip
        self.port = port
        self.conn = AdbDeviceTcp(ip, port, default_timeout_s=9.)

    ## context manager
    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def connect(self):
        self.conn.connect(rsa_keys=[self.signer], auth_timeout_s=0.1)

    def close(self):
        self.conn.close()

    def get_ss(self):
        """ Take screenshot and create image (PIL) object"""
        raw_bytes = self.conn.shell('screencap -p', decode=False).replace(b'\x0D\x0A', b'\x0A')
        return Image.open(BytesIO(raw_bytes))

    def get_theme_color(self):
        return self.get_dom_color_from_image(self.get_ss())
        #return self.get_avg_color_from_image(self.get_ss())

    def _get_signer(self, adbkeypath):
        with open(adbkeypath) as f:
            return PythonRSASigner('', f.read())



class RemoteDesktop(ImageSourceBase):
    # todo
    pass


class Desktop(ImageSourceBase):
    """ Get screenshot from desktop works only with windows and osx"""

    def __init__(self, *args):
        pass

    def get_theme_color(self):
        return self.get_avg_color_from_image(ImageGrab.grab())




