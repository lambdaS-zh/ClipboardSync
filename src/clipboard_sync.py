import socket
import struct
import sys
from monotonic import monotonic
from select import select as select_

import pyperclip


SELECT_TIMEOUT = 0.5  # seconds
CLIP_TIMEOUT = 0.1  # seconds
HEARTBEAT_INTERVAL = 60  # seconds
RECV_LEN = 8192
BIN_CODING = 'utf-8'
STREAM_MAGIC = b'\x41\x45\x38\x36'
HEADER_LEN = 4


class BadStream(ValueError):
    pass


class StreamHandler(object):

    def __init__(self):
        self._buf = b''

    def _on_idle(self, conn):
        pass

    def _pack_text(self, text):
        payload = text.encode(BIN_CODING)
        payload_len = len(payload)
        return STREAM_MAGIC + struct.pack('!I', payload_len) + payload

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

        text = self._buf[magic_len + HEADER_LEN:msg_len].decode(BIN_CODING)
        self._buf = self._buf[msg_len:]
        if text:
            # that means text is not heartbeat data
            pyperclip.copy(text)

    def _loop(self, conn):
        self._buf = b''
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
                    msg = self._pack_text(text)
                    conn.sendall(msg)
                    continue

                self._on_idle(conn)
        except BadStream:
            print('Bad stream. Clear this connection...')
        finally:
            conn.close()


class NetSyncClient(StreamHandler):

    def __init__(self, addr):
        super(NetSyncClient, self).__init__()
        self._addr = addr
        self._hb_stamp = monotonic()

    def _on_idle(self, conn):
        now = monotonic()
        if now - self._hb_stamp < HEARTBEAT_INTERVAL:
            return

        self._hb_stamp = now
        hb = self._pack_text('')
        conn.sendall(hb)

    def run(self):
        while True:
            conn = socket.socket()
            conn.connect(self._addr)
            self._loop(conn)


class NetSyncServer(StreamHandler):

    def __init__(self, addr):
        super(NetSyncServer, self).__init__()
        self._addr = addr

    def run(self):
        while True:
            server = socket.socket()
            try:
                server.bind(self._addr)
                server.listen(1)  # Always keeps only 1 connection.
                conn, remote = server.accept()
            finally:
                server.close()

            self._loop(conn)


def parse_addr(raw):
    if ':' not in raw:
        raise ValueError('Invalid addr: %s' % raw)
    return tuple(raw.split(':'))


if __name__ == '__main__':
    assert len(sys.argv) == 3
    kind, addr = sys.argv[1], sys.argv[2]
    assert kind in ('-c', '-s')

    addr = parse_addr(addr)

    if kind == '-c':
        NetSyncClient(addr).run()
    else:
        NetSyncServer(addr).run()

