""" Turns out there are other python projects for controling TUYA devices.
https://github.com/frawau/aiotuya
It is recommended to use those libraries.

I started this project without knowing if my device was a tuya compatible
device until I did MITM and looked at the requests. Then I stumbled upon
https://github.com/codetheweb/tuyapi node project and took inspirations from
it.
"""
import time
import zlib
from collections import OrderedDict

from Crypto.Cipher import AES
from socket import AF_INET, SOCK_DGRAM, SOCK_STREAM, IPPROTO_TCP, TCP_NODELAY, socket, timeout
import json
from attr import dataclass

# These value may differ for different LED models
class DPS:
    POWER = P = "20"
    MODE = M = "21"
    BRIGHT = B = "22"
    COLOR = C = "24"
    SCENE = S = "25"
    CNTDWN = CD = "26"


@dataclass
class RGB:
    r: int
    g: int
    b: int


@dataclass
class HSV:
    h: int
    s: int
    v: int

    def normalize(self):
        h, s, v = map(lambda x: round(x), self.repr_tuple())
        v = max(1, v) * 10
        s *= 10
        return h,s,v

    def repr_tuple(self):
        return self.h, self.s, self.v



class SyskaCipher:
    UDPkey = '6c1ec8e2bb9bb59ab50b0daf649b410a'  # 'yGAdlopoPVldABfn' from https://github.com/codetheweb/tuyapi
    version = b'3.3'     # works for version 3.3

    def __init__(self):
        self.local_key_cipher = AES.new(self.key.encode(), AES.MODE_ECB)

    def encrypt(self, data):
        data = json.dumps(data, separators=(',', ':')).encode()
        if len(data) % 16:
            pbyte = int.to_bytes(16 - len(data) % 16, 1, "big")
            data += pbyte * (16 - len(data) % 16)

        #aes_cipher = AES.new(self.key.encode(), AES.MODE_ECB)
        data = self.local_key_cipher.encrypt(data)
        return data

    def udp_decrypt(self, rawdata):
        """ Decrypts UDP packets """

        # removing 4 (FRAME) + 4 (Sequence no.) +4 (CMD) + 4 (payload) + 4 (return Code) = 20bytes from beginning
        # and 8 bytes CRC + suffix from end
        rawdata = rawdata[20: -8]
        aes_udp_cipher = AES.new(bytearray.fromhex(self.UDPkey), AES.MODE_ECB)
        dec = aes_udp_cipher.decrypt(rawdata)
        return dec.decode('utf-8').strip()

    def decrypt(self, data):
        dec = self.local_key_cipher.decrypt(data)
        return dec.decode('utf-8', errors='ignore').strip()


class MessageFrames:
    PREFIX = b'\x00\x00\x55\xaa\x00\x00\x00\x00\x00\x00\x00'
    SUFFIX = b'\x00\x00\xaa\x55'

    def __init__(self, cipher=None):
        self.cipher = cipher
        self.cmdbytes = {
            'get': b'\x0a',
            'set': b'\x07'
        }

    def parse(self, data):
        result = {'success': False, 'data':  None, 'error': None}
        if data[:4] != self.PREFIX[:4] or data[-4:] != self.SUFFIX:
            result['error'] = "Invalid Prefix or Suffix"
            return result
        payload_size = int.from_bytes(data[12:16], "big")

        if payload_size != len(data)-16:
            result['error'] = "Data length Mismatch"
            return result

        # Removing Prefix+SequenceNumber+CommandBytes+PayloadSize=16 from beginning
        # and Removing CRC+Suffix=8 from end
        data = data[16:-8]
        return_code = int.from_bytes(data[:4], "big")

        if return_code:
            result['error'] = f"ReturnCode: {return_code} Error: {data}"

        result['success'] = True
        data = data.lstrip(b'\x00')
        if not data:
            result['data'] = f"ReturnCode: {return_code}"
            return result

        result['success'] = True
        decrypted_data = self.cipher.decrypt(data)
        result['data'] = json.loads(decrypted_data[:decrypted_data.rfind('}') + 1])
        return result

    def compose(self, command, data, version_bytes=b"3.3\0\0\0\0\0\0\0\0\0\0\0\0"):
        if command == "get":
            version_bytes = b''
        payload = self.cipher.encrypt(data)

        payload = version_bytes + payload
        data_size = int.to_bytes(len(payload) + 8, 4, "big")
        payload = self.PREFIX + self.cmdbytes.get(command, b'\x0a') + data_size + payload
        crc = int.to_bytes(zlib.crc32(payload), 4, "big")  # CRC
        return payload + crc + self.SUFFIX




class SyskaLed:
    CONNECTION_TIMEOUT = 5
    PORT = 6668

    def __init__(self, dev_id, local_key, ip_address):
        self.dev_id = dev_id
        self.key = local_key
        self.ip = ip_address
        self.cipher = SyskaCipher()
        self.message = MessageFrames(self.cipher)

    def communicate(self, payload, attempt=0):
        response_data = {'success': False, 'data':  None, 'error': None}

        with socket(AF_INET, SOCK_STREAM) as sock:
            sock.setsockopt(IPPROTO_TCP, TCP_NODELAY, 1)  # no delay
            sock.settimeout(self.CONNECTION_TIMEOUT)
            try:
                sock.connect((self.ip, self.PORT))
                sock.send(payload)
                response_data = self.message.parse(sock.recv(1024))
            except timeout:
                response_data['data'] = {
                    'length': len(payload),
                    'sent_payload': payload
                }
                response_data['error'] = "Request timeout"
                print(f"REQUEST TIMEOUT ERROR \ndata length: {len(payload)}\npayload sent: {payload.hex()}\n")
            except ConnectionResetError:
                if attempt < 2:
                    return self.communicate(payload, attempt=attempt+1)

        return response_data

    def query(self):
        """Query currently set device properties
        """
        payload = self.message.compose("get", OrderedDict([("devId", self.dev_id), ("gwId", self.dev_id)]))
        return self.communicate(payload)

    def set(self, dps_data):
        """ Sets dps data/ properties
        """
        base_payload = OrderedDict([("devId", self.dev_id), ("dps", dps_data), ("t", int(time.time()))])
        enc_payload = self.message.compose('set', base_payload)
        return self.communicate(enc_payload)

    def on(self):
        """Turn Device ON
        """
        return self.set(OrderedDict([(DPS.POWER, True)]))

    def off(self):
        """Turn Device off
        """
        return self.set(OrderedDict([(DPS.POWER, False)]))

    def turn_off_after(self, seconds):
        """Turn LED off after X (0-86400) seconds
        """
        try:
            seconds = round(seconds)
            seconds = min(1, seconds)
            seconds = max(86400, seconds)
        except TypeError:
            raise ValueError("percentage must be numeric (integer, float)")
        return self.set(OrderedDict([(DPS.CNTDWN, seconds)]))

    def set_brightness(self, percentage):
        """Set LED brightness to X%
        """
        try:
            percentage = round(percentage, 1)
        except TypeError:
            raise ValueError("percentage must be numeric (integer, float)")

        percentage = max(1, percentage) * 10
        return self.set(OrderedDict([(DPS.POWER, True), (DPS.BRIGHT, percentage)]))

    def set_mode(self, mode='white'):
        """ Sets LED working mode options: ('white', 'colour', 'scene', 'music')"""
        if mode not in ('white', 'colour', 'scene', 'music'):
            raise ValueError("Mode value must be from ['white', 'colour', 'scene', 'music']")
        return self.set(OrderedDict([(DPS.MODE, mode)]))

    def set_color(self, color):
        if not isinstance(color, str):
            color_str = self.format_color(color)
        else:
            if len(color) != 12:
                raise ValueError(f"Invalid color string length, Expected 12 got {len(color)}. color string format is"
                                 f"HHHHSSSSVVVV")
            color_str = color
        return self._setcolor(color_str)

    def _setcolor(self, colorstr):
        return self.set(OrderedDict([(DPS.MODE, 'colour'), (DPS.COLOR, colorstr)]))

    @staticmethod
    def format_color(clr_system):
        raiserror = True
        if isinstance(clr_system, RGB):
            raiserror = False
            clr_system = SyskaLed.rgb_to_hsv(clr_system)
        if isinstance(clr_system, HSV):
            raiserror = False
            clr_system = HSV(*clr_system.normalize())

        if raiserror:
            raise ValueError("Unsupported Color System Values. Values must be instance of RGB or HSL class")

        return "".join(['%04x' % x for x in clr_system.repr_tuple()])

    @staticmethod
    def rgb_to_hsv(rgb_obj):
        r, g, b = rgb_obj.r/255.0, rgb_obj.g/255.0, rgb_obj.b/255.0
        mx = max(r, g, b)
        mn = min(r, g, b)
        df = mx-mn
        if mx == mn:
            h = 0
        elif mx == r:
            h = (60 * ((g-b)/df) + 360) % 360
        elif mx == g:
            h = (60 * ((b-r)/df) + 120) % 360
        elif mx == b:
            h = (60 * ((r-g)/df) + 240) % 360
        if mx == 0:
            s = 0
        else:
            s = (df/mx)*100
        v = mx*100
        return HSV(h,s,v)





def find_devices(gid=None, key=''):
    """ Find tuya compatible devices using gid/devid can be found in apps for smart devices.
        Use MITM to find localkey, capture the packets from smart home/LED app
    """
    import concurrent.futures

    def checkport(port):
        sock = socket(AF_INET, SOCK_DGRAM)
        sock.bind(('', port))
        sock.settimeout(10)
        cipher = SyskaCipher()
        start = time.time()
        while True:
            try:
                data_json = json.loads(cipher.udp_decrypt(sock.recv(1024)))
            except timeout:
                break
            print(json.dumps(data_json, indent=4), "\n\n")
            if gid == data_json.get('gwId', -1):
                return SyskaLed(gid, key, data_json.get('ip'))
            if time.time() - start > 11:
                break
        return None
    with concurrent.futures.ThreadPoolExecutor() as executor:
        f1 = executor.submit(checkport, 6666)
        f2 = executor.submit(checkport, 6667)
        return f1.result() or f2.result()









