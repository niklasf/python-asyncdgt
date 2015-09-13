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
import serial
import sys
import pyee
import glob
import logging
import pyee
import copy
import sys


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

DGT_CMD_CLOCK_BEEP = 0x0b

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


class Connection(pyee.EventEmitter):
    """
    Manages a DGT board connection.

    *port_globs* is a list of glob expressions like ``["/dev/ttyACM*"]``. When
    connecting the first successful match will be used.

    *loop* is the :mod:`asyncio` event loop.
    """

    def __init__(self, port_globs, loop):
        super().__init__()

        self.port_globs = list(port_globs)
        self.loop = loop

        self.serial = None
        self.board = Board()

        self.version_received = asyncio.Event(loop=loop)
        self.serialnr_received = asyncio.Event(loop=loop)
        self.long_serialnr_received = asyncio.Event(loop=loop)
        self.battery_status_received = asyncio.Event(loop=loop)
        self.board_received = asyncio.Event(loop=loop)

        self.closed = False
        self.connected = asyncio.Event(loop=loop)
        self.disconnect()

    def port_candidates(self):
        for port_glob in self.port_globs:
            yield from glob.iglob(port_glob)

    def connect(self):
        """Try to connect. Returns the connected port or ``False``."""
        for port in self.port_candidates():
            try:
                self.connect_port(port)
            except serial.SerialException:
                self.serial = None
                LOGGER.exception("Could not connect to port %s", port)
            else:
                return port

        return False

    def connect_port(self, port):
        self.closed = False
        self.disconnect()

        self.serial = serial.Serial(
            stopbits=serial.STOPBITS_ONE,
            parity=serial.PARITY_NONE,
            bytesize=serial.EIGHTBITS)

        self.serial.port = port

        # Close once first to allow reconnecting after an interrupted
        # connection.
        self.serial.close()
        self.serial.open()

        LOGGER.info("Connected to %s", port)
        self.emit("connected", port)

        self.loop.add_reader(self.serial, self.can_read)

        # Request initial board state and updates.
        self.serial.write(bytearray([DGT_SEND_UPDATE_NICE]))
        self.serial.write(bytearray([DGT_SEND_BRD]))

        self.connected.set()

    def close(self):
        """Close any open board connection."""
        self.closed = True
        self.disconnect()

    def disconnect(self):
        was_connected = self.serial is not None

        if was_connected:
            self.loop.remove_reader(self.serial)
            self.serial.close()

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

        self.message_id = 0
        self.message_buffer = b""
        self.remaining_message_length = 0

        self.connected.clear()

        if was_connected:
            LOGGER.info("Disconnected")
            self.emit("disconnected")

    def can_read(self):
        try:
            if not self.remaining_message_length:
                # Start of a new message.
                header = self.serial.read(3)
                self.message_id = header[0]
                self.remaining_message_length = (header[1] << 7) + header[2] - 3

            # Read remaining part of the current message.
            message = self.serial.read(self.remaining_message_length)
            self.remaining_message_length -= len(message)
            self.message_buffer += message
        except (TypeError, serial.SerialException):
            self.disconnect()
        else:
            # Full message received.
            if not self.remaining_message_length:
                self.process_message(self.message_id, self.message_buffer)
                self.message_buffer = b""

    def process_message(self, message_id, message):
        LOGGER.debug("Message %s: %s", hex(message_id), " ".join(format(c, "02x") for c in message))

        if message_id == MESSAGE_BIT | DGT_BOARD_DUMP:
            self.board.state = bytearray(message)
            self.board_received.set()
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
            self._process_bwtime(message)

    def _process_bwtime(self, message):
        if message[0] & 0x0f == 0x0A or message[3] == 0x0A:
            print("Clock ack!")
            ack0 = (message[1] & 0x7f) | (message[3] << 3) & 0x80
            ack1 = (message[2] & 0x7f) | (message[3] << 2) & 0x80
            ack2 = (message[4] & 0x7f) | (message[0] << 3) & 0x80
            ack3 = (message[5] & 0x7f) | (message[0] << 2) & 0x80
            if ack0 != 0x10:
                print("ACK ERROR!")
            else:
                print("CLOCK ACK!")

            if ack1 == 0x88:
                self.emit("button_pressed", int(chr(ack3)))
            elif ack1 == 0x09:
                print("Clock is there")
        elif any(message[:6]):
            print("Time received")
            r_hours = message[0] & 0x0f
            r_mins = (message[1] >> 4) * 10 + (message[1] & 0x0f)
            r_secs = (message[2] >> 4) * 10 + (message[2] & 0x0f)
            l_hours = message[3] & 0x0f
            l_mins = (message[4] >> 4) * 10 + (message[4] & 0x0f)
            l_secs = (message[5] >> 4) * 10 + (message[5] & 0x0f)
            print(r_hours, r_mins, r_secs, ":", l_hours, l_mins, l_secs)
        else:
            print("Other clock message")

    @asyncio.coroutine
    def get_version(self):
        """Get the board version."""
        self.version_received.clear()
        yield from self.connected.wait()
        self.serial.write(bytearray([DGT_SEND_VERSION]))
        yield from self.version_received.wait()
        return self.version

    @asyncio.coroutine
    def get_board(self):
        """Get the current board position as a :class:`asyncdgt.Board`."""
        self.board_received.clear()
        yield from self.connected.wait()
        self.serial.write(bytearray([DGT_SEND_BRD]))
        yield from self.board_received.wait()
        return self.board.copy()

    @asyncio.coroutine
    def get_serialnr(self):
        """Get the board serial number."""
        self.serialnr_received.clear()
        yield from self.connected.wait()
        self.serial.write(bytearray([DGT_RETURN_SERIALNR]))
        yield from self.serialnr_received.wait()
        return self.serialnr

    @asyncio.coroutine
    def get_long_serialnr(self):
        """Get the long variant of the board serial number."""
        self.long_serialnr_received.clear()
        yield from self.connected.wait()
        self.serial.write(bytearray([DGT_RETURN_LONG_SERIALNR]))
        yield from self.long_serialnr_received.wait()
        return self.long_serialnr

    @asyncio.coroutine
    def get_battery_status(self):
        self.battery_status_received.clear()
        yield from self.connected.wait()
        self.serial.write(bytearray([DGT_SEND_BATTERY_STATUS]))
        yield from self.battery_status_received.wait()
        return self.battery_status

    def clock_beep(self, ms=100):
        #self.serial.write([DGT_CLOCK_MESSAGE, 0x03, DGT_CMD_CLOCK_BEEP, 0x01, 0x00])
        pass

    def __enter__(self):
        if self.connect():
            return self
        else:
            raise IOError("dgt board not connected")

    def __exit__(self, exc_type, exc_value, traceback):
        return self.close()


def connect(port_globs, loop):
    """
    Creates a :class:`asyncdgt.Connection`.

    Raises :exc:`IOError` when no board can be connected.
    """
    return Connection(port_globs, loop).__enter__()


def auto_connect(port_globs, loop, max_backoff=10.0):
    """
    Creates a :class:`asyncdgt.Connection`.

    If no board is available or the board gets disconnected, reconnection
    attempts will be made with exponential backoff.

    *max_backoff* is the maximum expontential backoff time in seconds. The
    exponential backoff will not be increased beyond this.
    """
    dgt = Connection(port_globs, loop)

    @asyncio.coroutine
    def reconnect():
        backoff = 0.5
        connected = False

        while not connected and not dgt.closed:
            connected = dgt.connect()

            yield from asyncio.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)

    def on_disconnected():
        if not dgt.closed:
            _ = loop.create_task(reconnect())

    dgt.on("disconnected", on_disconnected)

    on_disconnected()

    return dgt
