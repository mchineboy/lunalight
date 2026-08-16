"""Small, synchronous client for VICE's binary monitor."""

from __future__ import annotations

import socket
import struct
import time


class ViceMonitor:
    """Drive a running VICE instance while preserving request ordering."""

    # Bank ids reported by BANKS_AVAILABLE; bank 0 follows CPU banking, so RAM
    # under the BASIC/KERNAL ROMs (VIC banks 2 and 3) needs the explicit RAM id.
    BANK_CPU = 0
    BANK_RAM = 1

    def __init__(self, host: str, port: int, timeout: float = 5.0):
        deadline = time.monotonic() + timeout
        while True:
            try:
                self.sock = socket.create_connection((host, port), timeout=1.0)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.05)
        self.sock.settimeout(timeout)
        self.request_id = 1
        self.events: list[tuple[int, int, int, bytes]] = []

    def close(self) -> None:
        self.sock.close()

    def _read_exact(self, size: int) -> bytes:
        chunks: list[bytes] = []
        while size:
            chunk = self.sock.recv(size)
            if not chunk:
                raise ConnectionError("VICE binary monitor disconnected")
            chunks.append(chunk)
            size -= len(chunk)
        return b"".join(chunks)

    def _packet(self) -> tuple[int, int, int, bytes]:
        header = self._read_exact(12)
        if header[:2] != b"\x02\x02":
            raise RuntimeError(f"invalid VICE response header: {header.hex()}")
        length = struct.unpack_from("<I", header, 2)[0]
        response_type, error = header[6], header[7]
        request_id = struct.unpack_from("<I", header, 8)[0]
        return response_type, error, request_id, self._read_exact(length)

    def command(
        self, command: int, body: bytes = b"", expected_response: int | None = None
    ) -> bytes:
        request_id = self.request_id
        self.request_id += 1
        expected_response = command if expected_response is None else expected_response
        header = b"\x02\x02" + struct.pack("<II", len(body), request_id)
        self.sock.sendall(header + bytes([command]) + body)
        while True:
            response_type, error, response_id, response_body = self._packet()
            if response_id != request_id:
                self.events.append(
                    (response_type, error, response_id, response_body)
                )
                continue
            if error:
                raise RuntimeError(
                    f"VICE monitor command ${command:02x} failed "
                    f"with error ${error:02x}"
                )
            if response_type != expected_response:
                raise RuntimeError(
                    f"VICE command ${command:02x} returned ${response_type:02x}"
                )
            return response_body

    def resume(self) -> None:
        self.command(0xAA)

    def banks(self) -> dict[str, int]:
        """Return the bank name to bank id mapping reported by VICE."""
        response = self.command(0x82)
        count = struct.unpack_from("<H", response, 0)[0]
        cursor = 2
        mapping: dict[str, int] = {}
        for _ in range(count):
            item_size = response[cursor]
            bank_id = struct.unpack_from("<H", response, cursor + 1)[0]
            name_length = response[cursor + 3]
            name = response[cursor + 4 : cursor + 4 + name_length].decode()
            mapping[name] = bank_id
            cursor += item_size + 1
        return mapping

    def memory_paused(self, start: int, end: int, bank: int = BANK_CPU) -> bytes:
        """Read memory and leave emulation stopped for an atomic snapshot."""
        body = struct.pack("<BHHBH", 0, start, end, 0, bank)
        response = self.command(0x01, body)
        count = struct.unpack_from("<H", response)[0]
        return response[2 : 2 + count]

    def memory(self, start: int, end: int, bank: int = BANK_CPU) -> bytes:
        data = self.memory_paused(start, end, bank)
        self.resume()
        return data

    def set_memory(self, start: int, data: bytes) -> None:
        end = start + len(data) - 1
        body = struct.pack("<BHHBH", 0, start, end, 0, 0) + data
        self.command(0x02, body)

    def inject_paused(self, text: bytes) -> None:
        """Inject PETSCII and leave VICE paused."""
        if not 1 <= len(text) <= 10:
            raise ValueError("C64 keyboard buffer accepts 1 to 10 bytes")
        self.set_memory(0x0277, text)
        self.set_memory(0x00C6, bytes([len(text)]))

    def inject(self, text: bytes) -> None:
        """Inject PETSCII through the C64 KERNAL keyboard buffer."""
        self.inject_paused(text)
        self.resume()

    def set_joyport(self, port: int, value: int) -> None:
        """Set VICE's simulated joystick bits and leave emulation paused."""
        if not 0 <= port <= 4:
            raise ValueError("joyport index must be 0..4")
        if not 0 <= value <= 0xFFFF:
            raise ValueError("joyport value must be 0..65535")
        self.command(0xA2, struct.pack("<HH", port, value))

    def stop_on_store(self, address: int) -> None:
        """Resume and stop exactly when the CPU next stores to an address."""
        body = struct.pack("<HHBBBBB", address, address, 1, 1, 2, 1, 0)
        self.command(0x12, body, expected_response=0x11)
        self.resume()
        hit = False
        stopped = False
        while not (hit and stopped):
            if self.events:
                response_type, error, response_id, _ = self.events.pop(0)
            else:
                response_type, error, response_id, _ = self._packet()
            if error:
                raise RuntimeError(
                    f"VICE asynchronous event failed with error ${error:02x}"
                )
            if response_id == 0xFFFFFFFF:
                hit = hit or response_type == 0x11
                stopped = stopped or response_type == 0x62

    def advance_instructions(self, count: int) -> None:
        """Advance a paused machine by an exact instruction count."""
        if not 1 <= count <= 0xFFFF:
            raise ValueError("instruction count must be 1..65535")
        self.command(0x71, struct.pack("<BH", 0, count))

    def palette(self) -> bytes:
        """Return the RGB palette associated with the display buffer."""
        response = self.command(0x91, b"\0")
        count = struct.unpack_from("<H", response, 0)[0]
        cursor = 2
        colors = bytearray()
        for _ in range(count):
            item_size = response[cursor]
            if item_size < 3:
                raise RuntimeError("VICE returned an invalid palette entry")
            colors.extend(response[cursor + 1 : cursor + 4])
            cursor += item_size + 1
        return bytes(colors)

    def display(self) -> tuple[int, int, bytes, dict[str, int]]:
        """Capture VICE's indexed 8-bit display buffer and its inner geometry.

        The buffer covers the whole frame including blanking; the inner screen
        is the visible display area reported by VICE at an offset inside it.
        """
        response = self.command(0x84, b"\0\0")
        info_length = struct.unpack_from("<I", response, 0)[0]
        width, height = struct.unpack_from("<HH", response, 4)
        x_offset, y_offset, inner_width, inner_height = struct.unpack_from(
            "<HHHH", response, 8
        )
        bits_per_pixel = response[16]
        pixel_length = struct.unpack_from("<I", response, 17)[0]
        pixel_start = 4 + info_length
        pixels = response[pixel_start : pixel_start + pixel_length]
        if bits_per_pixel != 8 or len(pixels) != width * height:
            raise RuntimeError(
                f"unsupported VICE display: {width}x{height}x{bits_per_pixel}"
            )
        self.resume()
        return (
            width,
            height,
            pixels,
            {
                "x_offset": x_offset,
                "y_offset": y_offset,
                "width": inner_width,
                "height": inner_height,
            },
        )

    def quit(self) -> None:
        """Request a normal VICE exit, allowing exit hooks to run."""
        try:
            self.command(0xBB)
        except ConnectionError:
            # Some VICE versions close the socket before sending the response.
            pass
