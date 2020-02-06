import select
import socket
import threading
from ssl import SSLContext
from typing import Dict, Optional

from .._exceptions import (
    CloseError,
    ConnectError,
    ConnectTimeout,
    ReadError,
    ReadTimeout,
    WriteError,
    WriteTimeout,
    map_exceptions,
)


class SyncSocketStream:
    """
    A socket stream with read/write operations. Abstracts away any asyncio-specific
    interfaces into a more generic base class, that we can use with alternate
    backends, or for stand-alone test cases.
    """

    def __init__(self, sock: socket.socket) -> None:
        self.sock = sock
        self.read_lock = threading.Lock()
        self.write_lock = threading.Lock()

    def read(self, n: int, timeout: Dict[str, Optional[float]]) -> bytes:
        read_timeout = timeout.get("read")
        exc_map = {socket.timeout: ReadTimeout, socket.error: ReadError}

        with self.read_lock:
            with map_exceptions(exc_map):
                self.sock.settimeout(read_timeout)
                return self.sock.recv(n)

    def write(self, data: bytes, timeout: Dict[str, Optional[float]]) -> None:
        write_timeout = timeout.get("write")
        exc_map = {socket.timeout: WriteTimeout, socket.error: WriteError}

        with self.write_lock:
            with map_exceptions(exc_map):
                while data:
                    self.sock.settimeout(write_timeout)
                    n = self.sock.send(data)
                    data = data[n:]

    def close(self) -> None:
        with self.write_lock:
            with map_exceptions({socket.error: CloseError}):
                self.sock.close()

    def is_connection_dropped(self) -> bool:
        rready, _wready, _xready = select.select([self.sock], [], [], 0)
        return bool(rready)


class SyncBackend:
    def open_tcp_stream(
        self,
        hostname: bytes,
        port: int,
        ssl_context: Optional[SSLContext],
        timeout: Dict[str, Optional[float]],
    ) -> SyncSocketStream:
        connect_timeout = timeout.get("connect")
        exc_map = {socket.timeout: ConnectTimeout, socket.error: ConnectError}

        with map_exceptions(exc_map):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(connect_timeout)
            sock.connect((hostname.decode("ascii"), port))
            if ssl_context is not None:
                sock = ssl_context.wrap_socket(
                    sock, server_hostname=hostname.decode("ascii")
                )
            return SyncSocketStream(sock=sock)
