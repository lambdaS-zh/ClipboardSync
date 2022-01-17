import socket
import struct
from select import select as select_

import pyperclip


SELECT_TIMEOUT = 0.5  # seconds
CLIP_TIMEOUT = 0.1  # seconds
RECV_LEN = 8192
STREAM_MAGIC = b'\x41\x45\x38\x36'
HEADER_LEN = 4


class BadStream(ValueError):
    pass


class SyncAgent(object):

    def on_local_copy(self, text):
        self.send_to_remote(data)

    def send_to_remote(self, data):
        raise NotImplementedError()

    def on_recv_from_remote(self, data):
        pyperclip.copy(data)


class NetSyncClient(SyncAgent):
    pass


class NetSyncServer(object):

    def __init__(self, addr):
        self._addr = addr
        self._buf = b''

    def _on_recv_data(self, data):
        magic_len = len(STREAM_MAGIC)
        self._buf += data
        if len(self._buf) < magic_len:
            return
        if not self._buf.startswith(STREAM_MAGIC):
            raise BadStream()

        if len(self._buf) < magic_len + HEADER_LEN:
            return
        header = self._buf[magic_len:magic_len + HEADER_LEN]
        payload_len = struct.unpack('!I', header)

        msg_len = magic_len + HEADER_LEN + payload_len
        if len(self._buf) < msg_len:
            return

        text = self._buf[magic_len + HEADER_LEN:msg_len].decode('utf-8')
        self._buf = self._buf[msg_len:]
        if text:
            # that means text is not heartbeat data
            pyperclip.copy(text)

    def run(self):
        while True:
            server = socket.socket()
            try:
                server.bind(self._addr)
                server.listen(1)  # Always keeps only 1 connection.
                conn, remote = server.accept()
            finally:
                server.close()

            conn.setblocking(False)
            try:
                while True:
                    r_, _w, _e = select_([conn], [], [], SELECT_TIMEOUT)

                    if r_:
                        data = conn.recv(RECV_LEN)
                        if not data:
                            break
                        self._on_recv_data(data)
                        continue

                    try:
                        text = pyperclip.waitForNewPaste(CLIP_TIMEOUT)
                    except pyperclip.PyperclipTimeoutException:
                        pass
                    else:
                        conn.sendall(text.encode('utf-8'))
            finally:
                conn.close()

