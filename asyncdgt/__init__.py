#!/usr/bin/env python

import asyncio
import serial
import sys
import pyee
import glob
import logging
import pyee
import copy
import sys
import codecs


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

    def __init__(self, board_fen=None):
        self.state = bytearray(0x00 for _ in range(64))
        if board_fen:
            self.set_board_fen(board_fen)

    def board_fen(self):
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

    def set_board_fen(self):
        pass

    def clear(self):
        self.state = bytearray(0x00 for _ in range(64))

    def copy(self):
        return copy.deepcopy(self)

    def __str__(self):
        return self.board_fen()

    def __repr__(self):
        return "Board({0})".format(repr(self.board_fen()))


class Connection(pyee.EventEmitter):

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
        self.disconnect()

    def port_candidates(self):
        for port_glob in self.port_globs:
            yield from glob.iglob(port_glob)

    def connect(self):
        for port in self.port_candidates():
            try:
                self.connect_port(port)
            except serial.SerialException:
                LOGGER.exception("Could not connect to port %s", port)
            else:
                return port

        return False

    def connect_port(self, port):
        self.closed = False
        self.disconnect()

        self.serial = serial.Serial(port,
            stopbits=serial.STOPBITS_ONE,
            parity=serial.PARITY_NONE,
            bytesize=serial.EIGHTBITS)

        LOGGER.info("Connected to %s", port)
        self.emit("connected", port)

        self.loop.add_reader(self.serial, self.can_read)

        # Request initial board state and updates.
        self.serial.write(bytearray([DGT_SEND_UPDATE_NICE]))
        self.serial.write(bytearray([DGT_SEND_BRD]))

        self.clock_beep()

    def close(self):
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
        LOGGER.debug("Message %s: %s", hex(message_id), codecs.encode(message, "hex"))

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

    @asyncio.coroutine
    def get_version(self):
        self.version_received.clear()
        self.serial.write(bytearray([DGT_SEND_VERSION]))
        yield from self.version_received.wait()
        return self.version

    @asyncio.coroutine
    def get_board(self):
        self.board_received.clear()
        self.serial.write(bytearray([DGT_SEND_BRD]))
        yield from self.board_received.wait()
        return self.board.copy()

    @asyncio.coroutine
    def get_serialnr(self):
        self.serialnr_received.clear()
        self.serial.write(bytearray([DGT_RETURN_SERIALNR]))
        yield from self.serialnr_received.wait()
        return self.serialnr

    @asyncio.coroutine
    def get_long_serialnr(self):
        self.long_serialnr_received.clear()
        self.serial.write(bytearray([DGT_RETURN_LONG_SERIALNR]))
        yield from self.long_serialnr_received.wait()
        return self.long_serialnr

    @asyncio.coroutine
    def get_battery_status(self):
        self.battery_status_received.clear()
        self.serial.write(bytearray([DGT_SEND_BATTERY_STATUS]))
        yield from self.battery_status_received.wait()
        return self.battery_status

    def clock_beep(self, ms=100):
        #self.serial.write([DGT_CLOCK_MESSAGE, 0x03, DGT_CMD_CLOCK_BEEP, 0x01, 0x00])
        pass


def connect(port_globs, loop):
    dgt = Connection(port_globs, loop)

    if not dgt.connect():
        raise IOError("dgt not connected")

    return dgt


def auto_connect(port_globs, loop):
    dgt = Connection(port_globs, loop)

    @asyncio.coroutine
    def reconnect():
        backoff = 0.5
        connected = False

        while not connected and not dgt.closed:
            print("Trying to connect")
            connected = dgt.connect()

            yield from asyncio.sleep(backoff)
            backoff = min(backoff * 2, 10)

    def on_disconnected():
        if not dgt.closed:
            _ = loop.create_task(reconnect())

    dgt.on("disconnected", on_disconnected)

    on_disconnected()

    return dgt
