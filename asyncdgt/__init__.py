# -*- coding: utf-8 -*-
# This file is part of the python-asyncdgt library.
# Copyright (C) Niklas Fiekas <niklas.fiekas@tu-clausthal.de>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

"""
Communicate asynchronously with DGT boards.
"""

__author__ = "Niklas Fiekas"

__email__ = "niklas.fiekas@tu-clausthal.de"

__version__ = "0.0.1"


import asyncio
import collections
import serial
import serial.tools.list_ports
import sys
import pyee
import glob
import fnmatch
import logging
import pyee
import copy
import sys
import os
import itertools
import fcntl
import termios
import threading
import queue


DGT_SEND_RESET = 0x40
DGT_SEND_BRD = 0x42
DGT_SEND_UPDATE_BRD = 0x44
DGT_SEND_UPDATE_NICE = 0x4b
DGT_RETURN_SERIALNR = 0x45
DGT_RETURN_LONG_SERIALNR = 0x55
DGT_SEND_BATTERY_STATUS = 0x4C
DGT_SEND_VERSION = 0x4D

DGT_FONE = 0x00
DGT_BOARD_DUMP = 0x06
DGT_BWTIME = 0x0D
DGT_FIELD_UPDATE = 0x0E
DGT_EE_MOVES = 0x0F
DGT_BUSADRES = 0x10
DGT_SERIALNR = 0x11
DGT_LONG_SERIALNR = 0x22
DGT_TRADEMARK = 0x12
DGT_VERSION = 0x13
DGT_BOARD_DUMP_50B = 0x14
DGT_BOARD_DUMP_50W = 0x15
DGT_BATTERY_STATUS = 0x20
DGT_LONG_SERIALNR = 0x22

MESSAGE_BIT = 0x80

DGT_CLOCK_MESSAGE = 0x2b
DGT_CLOCK_START_MESSAGE = 0x03
DGT_CLOCK_END_MESSAGE = 0x00
DGT_CLOCK_DISPLAY = 0x01
DGT_CLOCK_BEEP = 0x0b
DGT_CLOCK_ASCII = 0x0c
DGT_CLOCK_SEND_VERSION = 0x09

PIECE_TO_CHAR = {
    0x01: "P",
    0x02: "R",
    0x03: "N",
    0x04: "B",
    0x05: "K",
    0x06: "Q",
    0x07: "p",
    0x08: "r",
    0x09: "n",
    0x0a: "b",
    0x0b: "k",
    0x0c: "q",
}

LOGGER = logging.getLogger(__name__)


class Board(object):
    """
    A position on the board.

    >>> board = asyncdgt.Board("rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR")
    >>> print(board)
    r n b k q b n r
    p p p p p p p p
    . . . . . . . .
    . . . . . . . .
    . . . P . . . .
    . . . . . . . .
    P P P . P P P .
    R N B Q K B N R
    """

    def __init__(self, board_fen=None):
        self.state = bytearray(0x00 for _ in range(64))
        if board_fen:
            self.set_board_fen(board_fen)

    def board_fen(self):
        """
        Gets the FEN of the position.

        >>> board = asyncdgt.Board()
        >>> board.board_fen()
        '8/8/8/8/8/8/8/8'
        """
        fen = []
        empty = 0

        for index, c in enumerate(self.state):
            if not c:
                empty += 1

            if empty > 0 and (c or (index + 1) % 8 == 0):
                fen.append(str(empty))
                empty = 0

            if c:
                fen.append(PIECE_TO_CHAR[c])

            if (index + 1) % 8 == 0 and index < 63:
                fen.append("/")

        return "".join(fen)

    def set_board_fen(self, fen):
        """Set a FEN."""
        # Ensure there are enough rows.
        rows = fen.split("/")
        if len(rows) != 8:
            raise ValueError("expected 8 rows in the fen: {0}".format(repr(fen)))


        # Validate each row.
        for row in rows:
            field_sum = 0
            previous_was_digit = False

            for c in row:
                if c in ["1", "2", "3", "4", "5", "6", "7", "8"]:
                    if previous_was_digit:
                        raise ValueError("two subsequent digits in the fen: {0}".format(repr(fen)))
                    field_sum += int(c)
                    previous_was_digit = True
                elif c in PIECE_TO_CHAR.values():
                    field_sum += 1
                    previous_was_digit = False
                else:
                    raise ValueError("invalid character in the fen: {0}".format(repr(fen)))

            if field_sum != 8:
                raise ValueError("expected 8 columns per row in fen: {0}".format(repr(fen)))

        # Put the pieces on the board.
        self.clear()
        square_index = 0
        for c in fen:
            if c in ["1", "2", "3", "4", "5", "6", "7", "8"]:
                square_index += int(c)
            elif c != "/":
                for piece_code, char in PIECE_TO_CHAR.items():
                    if c == char:
                        self.state[square_index] = piece_code
                        break
                else:
                    assert False

                square_index += 1

    def clear(self):
        """Clear the board."""
        self.state = bytearray(0x00 for _ in range(64))

    def copy(self):
        """Get a copy of the board."""
        return copy.deepcopy(self)

    def __str__(self):
        builder = []

        for square_index in range(0, 64):
            if self.state[square_index]:
                builder.append(PIECE_TO_CHAR[self.state[square_index]])
            else:
                builder.append(".")

            if square_index == 63:
                pass
            elif square_index % 8 == 7:
                builder.append("\n")
            else:
                builder.append(" ")

        return "".join(builder)

    def __repr__(self):
        return "Board({0})".format(repr(self.board_fen()))

    def __eq__(self, other):
        return not self.__ne__(other)

    def __ne__(self, other):
        if other is None:
            return True

        return self.state != other.state


class Clock(collections.namedtuple("Clock", ["left_time", "right_time", "left_up"])):
    """
    The status of the clock.

    *left_time* is the remaining time for the left side in seconds.

    *right_time* is the remaining time for the right side in seconds.

    *left_up* is information about the status of the lever.
    """
    pass


class AsyncDriver(object):
    """Provides fully asynchronous serial communication."""

    def __init__(self, connection):
        self.connection = connection
        self.disconnect()

    def configure_serial(self):
        self.connection.serial.timeout = 0
        self.connection.serial.writeTimeout = 0

    def connect(self, port):
        # Hook serial device into event loop.
        self.connection.loop.add_reader(self.connection.serial, self.can_read)

    def disconnect(self):
        if self.connection.serial:
            self.connection.loop.remove_reader(self.connection.serial)
            self.connection.loop.remove_writer(self.connection.serial)

        self.message_id = 0
        self.header_buffer = b""
        self.message_buffer = b""
        self.remaining_header_length = 3
        self.remaining_message_length = 0

        self.write_buffer = b""

    def can_read(self):
        try:
            # Partial header.
            if self.remaining_header_length:
                header_part = self.connection.serial.read(self.remaining_header_length)
                self.header_buffer += header_part
                self.remaining_header_length -= len(header_part)

            # Header complete.
            if not self.remaining_header_length and not self.message_buffer:
                self.message_id = self.header_buffer[0]
                self.remaining_message_length = (self.header_buffer[1] << 7) + self.header_buffer[2] - 3

            # Partial message.
            if not self.remaining_header_length and self.remaining_message_length:
                message_part = self.connection.serial.read(self.remaining_message_length)
                self.message_buffer += message_part
                self.remaining_message_length -= len(message_part)
        except (TypeError, OSError, serial.SerialException):
            LOGGER.exception("Error reading from serial port")
            self.connection.disconnect()
        else:
            # Message complete.
            if not self.remaining_header_length and not self.remaining_message_length:
                self.connection.process_message(self.message_id, self.message_buffer)
                self.header_buffer = b""
                self.remaining_header_length = 3
                self.message_buffer = b""

    def write(self, buf):
        # Start writer.
        if not self.write_buffer:
            self.connection.loop.add_writer(self.connection.serial, self.can_write)

        # Append to buffer.
        self.write_buffer += buf

    def can_write(self):
        try:
            # Write as much as possible without blocking.
            bytes_written = self.connection.serial.write(self.write_buffer)
            LOGGER.debug("Sent: %s", " ".join(format(c, "02x") for c in self.write_buffer[:bytes_written]))
        except (TypeError, OSError, serial.SerialException):
            # Connection failed.
            LOGGER.exception("Error writing to serial port")
            self.connection.disconnect()
        else:
            # Remove written bytes from buffer.
            self.write_buffer = self.write_buffer[bytes_written:]
        finally:
            # Stop writer.
            if not self.write_buffer:
                self.connection.loop.remove_writer(self.connection.serial)


class ThreadedDriver(object):
    """Fallback. Provides threaded serial communication."""

    def __init__(self, connection):
        self.connection = connection
        self.write_queue = queue.Queue()
        self.connected = False

        self.shutdown_marker = object()

    def configure_serial(self):
        self.connection.serial.timeout = None
        self.connection.serial.writeTimeout = None

    def disconnect(self):
        # No longer connected.
        self.connected = False

        # Clear the write queue.
        while not self.write_queue.empty():
            self.write_queue.get_nowait()

        # Wake up the write queue.
        self.write_queue.put(self.shutdown_marker)

    def connect(self, port):
        if self.connected:
            return

        self.connected = True

        # Clear the write queue.
        while not self.write_queue.empty():
            self.write_queue.get_nowait()

        self.write_thread = threading.Thread(target=self.write_loop)
        self.write_thread.daemon = True
        self.write_thread.start()

        self.read_thread = threading.Thread(target=self.read_loop)
        self.read_thread.daemon = True
        self.read_thread.start()

    def write(self, buf):
        self.write_queue.put(buf)

    def write_loop(self):
        try:
            while self.connected:
                buf = self.write_queue.get()
                if buf is self.shutdown_marker:
                    break

                self.connection.serial.write(buf)
                self.write_queue.task_done()
        except (TypeError, OSError, serial.SerialException):
            LOGGER.exception("Error writing to serial port")
            self.connection.loop.call_soon_threadsafe(self.connection.disconnect)

    def read_loop(self):
        try:
            while self.connected:
                header = self.connection.serial.read(3)
                message_id = header[0]
                message_length = (header[1] << 7) +  header[2]

                message = self.connection.serial.read(message_length - 3)

                self.connection.loop.call_soon_threadsafe(self.connection.process_message, message_id, message)
        except (TypeError, OSError, serial.SerialException):
            LOGGER.exception("Error reading from serial port")
            self.connection.loop.call_soon_threadsafe(self.connection.disconnect)


class Connection(pyee.EventEmitter):
    """
    Manages a DGT board connection.

    *loop* is the :mod:`asyncio` event loop.

    *port_globs* is a list of glob expressions like ``["/dev/ttyACM*"]``. When
    connecting the first successful match will be used.
    """

    def __init__(self, loop, port_globs, lock_port=False):
        super().__init__()

        self.loop = loop
        self.port_globs = list(port_globs)
        self.lock_port = lock_port

        self.serial = None
        self.board = Board()

        if os.name not in ["nt"]:
            self.driver = AsyncDriver(self)
        else:
            logging.info("Using threaded driver on Windows")
            self.driver = ThreadedDriver(self)

        self.version_received = asyncio.Event(loop=loop)
        self.serialnr_received = asyncio.Event(loop=loop)
        self.long_serialnr_received = asyncio.Event(loop=loop)
        self.battery_status_received = asyncio.Event(loop=loop)
        self.board_received = asyncio.Event(loop=loop)
        self.clock_version_received = asyncio.Event(loop=loop)
        self.clock_ack_received = asyncio.Event(loop=loop)

        self.clock_lock = asyncio.Lock(loop=loop)

        self.closed = False
        self.connected = asyncio.Event(loop=loop)
        self.disconnect()

    def port_candidates(self):
        # Match in the filesystem.
        for port_glob in self.port_globs:
            yield from glob.iglob(port_glob)

        # Match the list of known serial devices.
        for dev, _, _ in serial.tools.list_ports.comports():
            for port_glob in self.port_globs:
                if fnmatch.fnmatch(dev, port_glob):
                    yield dev
                    break

    def unique_port_candidates(self):
        seen = set()
        for port in itertools.filterfalse(seen.__contains__, self.port_candidates()):
            seen.add(port)
            yield port

    def connect(self):
        """Try to connect. Returns the connected port or ``False``."""
        for port in self.unique_port_candidates():
            try:
                self.connect_port(port)
            except serial.SerialException as err:
                self.serial = None
                LOGGER.error("Could not connect to port %s: %s", port, err)
            else:
                return port

        return False

    def connect_port(self, port):
        # Clean up possible previous connections.
        self.closed = False
        self.disconnect()

        # Configure port.
        self.serial = serial.Serial(
            baudrate=9600,
            stopbits=serial.STOPBITS_ONE,
            parity=serial.PARITY_NONE,
            bytesize=serial.EIGHTBITS)

        self.driver.configure_serial()
        self.serial.port = port

        # Close once first to allow reconnecting after an interrupted
        # connection.
        self.serial.close()
        self.serial.open()

        # Lock serial port.
        if self.lock_port:
            try:
                fcntl.ioctl(self.serial.fd, termios.TIOCEXCL)
            except OSError:
                LOGGER.warning("Could not set TIOCEXCL on port", self.serial.fd)

        # Notify driver of new connection.
        self.driver.connect(port)

        # Request initial board state and updates.
        self.write(bytearray([DGT_SEND_UPDATE_NICE]))
        self.write(bytearray([DGT_SEND_BRD]))

        # Fire connected event.
        LOGGER.info("Connected to %s", port)
        self.emit("connected", port)
        self.connected.set()

    def close(self):
        """Close any open board connection."""
        self.closed = True
        self.disconnect()

    def disconnect(self):
        was_connected = self.serial is not None

        self.driver.disconnect()

        if was_connected:
            # Release serial port.
            if self.lock_port:
                try:
                    fcntl.ioctl(self.serial.fd, termios.TIOCNXCL)
                except OSError:
                    LOGGER.warning("Could not set TIOCNXCL on port")

            self.serial.close()

        self.serial = None

        self.version_received.clear()
        self.version = None

        self.serialnr_received.clear()
        self.serialnr = None

        self.long_serialnr_received.clear()
        self.long_serialnr = None

        self.battery_status_received.clear()
        self.battery_status = None

        self.board_received.clear()
        self.board.clear()

        self.clock_version_received.clear()
        self.clock_version = None

        self.clock_ack_received.clear()

        self.clock_state = None
        self.board_state = None

        self.connected.clear()

        if was_connected:
            LOGGER.info("Disconnected")
            self.emit("disconnected")

    def write(self, buf):
        return self.driver.write(buf)

    def process_message(self, message_id, message):
        LOGGER.debug("Message %s: %s", hex(message_id), " ".join(format(c, "02x") for c in message))

        if message_id == MESSAGE_BIT | DGT_BOARD_DUMP:
            self.board.state = bytearray(message)
            self.board_received.set()
            if self.board != self.board_state:
                self.board_state = self.board
                self.emit("board", self.board.copy())
        elif message_id == MESSAGE_BIT | DGT_FIELD_UPDATE:
            self.board.state[message[0]] = message[1]
            self.emit("board", self.board.copy())
        elif message_id == MESSAGE_BIT | DGT_VERSION:
            self.version = "%d.%d" % (message[0], message[1])
            self.version_received.set()
        elif message_id == MESSAGE_BIT | DGT_SERIALNR:
            self.serialnr = "".join(chr(c) for c in message)
            self.serialnr_received.set()
        elif message_id == MESSAGE_BIT | DGT_LONG_SERIALNR:
            self.long_serialnr = "".join(chr(c) for c in message)
            self.long_serialnr_received.set()
        elif message_id == MESSAGE_BIT | DGT_BATTERY_STATUS:
            self.battery_status = "".join(chr(c) for c in message if c)
            self.battery_status_received.set()
        elif message_id == MESSAGE_BIT | DGT_BWTIME:
            self.process_bwtime(message)

    def process_bwtime(self, message):
        if message[0] & 0x0f == 0x0A or message[3] == 0x0A:
            # Handle Clock ACKs.
            ack0 = (message[1] & 0x7f) | (message[3] << 3) & 0x80
            ack1 = (message[2] & 0x7f) | (message[3] << 2) & 0x80
            ack2 = (message[4] & 0x7f) | (message[0] << 3) & 0x80
            ack3 = (message[5] & 0x7f) | (message[0] << 2) & 0x80
            if ack0 != 0x10:
                LOGGER.warning("Clock ACK error")
                return
            else:
                self.clock_ack_received.set()

            if ack1 == 0x88:
                # Button pressed.
                self.emit("button_pressed", int(chr(ack3)))
            elif ack1 == 0x09:
                # Version received.
                self.clock_version = "{0}.{1}".format(ack2 >> 4, ack2 & 0x0f)
                self.clock_version_received.set()
        elif any(message[:6]):
            # Clock time updated.
            r_hours = message[0] & 0x0f
            r_mins = (message[1] >> 4) * 10 + (message[1] & 0x0f)
            r_secs = (message[2] >> 4) * 10 + (message[2] & 0x0f)
            l_hours = message[3] & 0x0f
            l_mins = (message[4] >> 4) * 10 + (message[4] & 0x0f)
            l_secs = (message[5] >> 4) * 10 + (message[5] & 0x0f)

            l_down = message[6] & 0x10

            clock_state = Clock(
                l_hours * 60 * 60 + l_mins * 60 + l_secs,
                r_hours * 60 * 60 + r_mins * 60 + r_secs,
                bool(l_down))

            if self.clock_state != clock_state:
                self.clock_state = clock_state
                self.emit("clock", clock_state)
        else:
            LOGGER.warning("Unknown clock message")

    @asyncio.coroutine
    def get_version(self):
        """Coroutine. Get the board version."""
        self.version_received.clear()
        yield from self.connected.wait()
        self.write(bytearray([DGT_SEND_VERSION]))
        yield from self.version_received.wait()
        return self.version

    @asyncio.coroutine
    def get_board(self):
        """
        Coroutine. Get the current board position as a :class:`asyncdgt.Board`.
        """
        self.board_received.clear()
        yield from self.connected.wait()
        self.write(bytearray([DGT_SEND_BRD]))
        yield from self.board_received.wait()
        return self.board.copy()

    @asyncio.coroutine
    def get_serialnr(self):
        """Coroutine. Get the board serial number."""
        self.serialnr_received.clear()
        yield from self.connected.wait()
        self.write(bytearray([DGT_RETURN_SERIALNR]))
        yield from self.serialnr_received.wait()
        return self.serialnr

    @asyncio.coroutine
    def get_long_serialnr(self):
        """Coroutine. Get the long variant of the board serial number."""
        self.long_serialnr_received.clear()
        yield from self.connected.wait()
        self.write(bytearray([DGT_RETURN_LONG_SERIALNR]))
        yield from self.long_serialnr_received.wait()
        return self.long_serialnr

    @asyncio.coroutine
    def get_clock_version(self):
        """Coroutine. Get the clock version."""
        self.clock_version_received.clear()
        yield from self.connected.wait()
        self.write(bytearray([
            DGT_CLOCK_MESSAGE, 3,
            DGT_CLOCK_START_MESSAGE,
            DGT_CLOCK_SEND_VERSION,
            DGT_CLOCK_END_MESSAGE,
        ]))
        yield from self.clock_version_received.wait()
        return self.clock_version

    @asyncio.coroutine
    def clock_beep(self, seconds=0.064):
        """Coroutine. Let the clock beep."""
        seconds = min(seconds, 10.0)
        ms = seconds * 1000
        intervals = max(int(round(ms / 64)), 1)

        yield from self.connected.wait()

        with (yield from self.clock_lock):
            self.clock_ack_received.clear()
            self.write(bytearray([
                DGT_CLOCK_MESSAGE, 4,
                DGT_CLOCK_START_MESSAGE,
                DGT_CLOCK_BEEP,
                intervals,
                DGT_CLOCK_END_MESSAGE,
            ]))
            yield from asyncio.sleep(intervals * 0.064)
            yield from self.clock_ack_received.wait()

    @asyncio.coroutine
    def clock_text(self, text_dgt_xl, text_dgt_3000=None):
        """
        Coroutine. Display ASCII text on the clock.

        *text_dgt_xl* should consist of at most 6 ASCII characters.

        An optional longer 8 character version of the string can be provided
        for the DGT 3000 clock.
        """
        if text_dgt_3000 is None:
            text_dgt_3000 = text_dgt_xl

        yield from self.connected.wait()

        if not self.clock_version:
            yield from self.get_clock_version()

        with (yield from self.clock_lock):
            if self.clock_version.startswith("2."):
                # DGT 3000.
                t = _center_text(text_dgt_3000, 8)
                self.write(bytearray([
                    DGT_CLOCK_MESSAGE, 12,
                    DGT_CLOCK_START_MESSAGE,
                    DGT_CLOCK_ASCII,
                ] + [c for c in t] + [
                    0x01,
                    DGT_CLOCK_END_MESSAGE,
                ]))
            else:
                # DGT XL.
                t = _center_text(text_dgt_xl, 6)
                self.write(bytearray([
                    DGT_CLOCK_MESSAGE, 11,
                    DGT_CLOCK_START_MESSAGE,
                    DGT_CLOCK_DISPLAY,
                    t[2], t[1], t[0], t[5], t[4], t[3], 0x00,
                    0x01,
                    DGT_CLOCK_END_MESSAGE
                ]))

    def __enter__(self):
        if self.connect():
            return self
        else:
            raise IOError("dgt board not connected")

    def __exit__(self, exc_type, exc_value, traceback):
        return self.close()


def _center_text(text, display_size):
    text = text.ljust((len(text) + display_size) // 2).rjust(display_size)
    bytestr = text.encode("ascii")
    if len(bytestr) > display_size:
        LOGGER.warning("Text %s exceeds display size of %d", repr(text), display_size)
        return bytestr[0:8]
    else:
        return bytestr


def connect(loop, port_globs):
    """
    Creates a :class:`asyncdgt.Connection`.

    Raises :exc:`IOError` when no board can be connected.
    """
    return Connection(loop, port_globs).__enter__()


def auto_connect(loop, port_globs, lock_port=False, max_backoff=10.0):
    """
    Creates a :class:`asyncdgt.Connection`.

    If no board is available or the board gets disconnected, reconnection
    attempts will be made with exponential backoff.

    *max_backoff* is the maximum expontential backoff time in seconds. The
    exponential backoff will not be increased beyond this.
    """
    dgt = Connection(loop, port_globs, lock_port=lock_port)

    @asyncio.coroutine
    def reconnect():
        backoff = 0.5
        connected = False

        while not dgt.closed:
            LOGGER.debug("Trying to connect")
            connected = dgt.connect()
            if connected:
                break

            yield from asyncio.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)

    def on_disconnected():
        if not dgt.closed:
            LOGGER.debug("Reconnection attempts will be scheduled")
            _ = loop.create_task(reconnect())

    dgt.on("disconnected", on_disconnected)

    on_disconnected()

    return dgt
