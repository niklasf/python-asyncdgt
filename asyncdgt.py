#!/usr/bin/env python

import asyncio
import serial
import sys
import pyee
import glob
import logging

#import chess

DGT_SEND_BRD = 0x42

DGT_BOARD_DUMP = 0x86

DGT_SEND_UPDATE_NICE = 0x4b

DGT_MSG_FIELD_UPDATE = 0x80 | 0x0e

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

class Board(object):

    def __init__(self):
        self.state = bytearray(0x00 for _ in range(64))

    def process_message(self, message_id, message):
        print(hex(message_id), message)
        if message_id == DGT_BOARD_DUMP:
            self.state = bytearray(message)
        elif message_id == DGT_MSG_FIELD_UPDATE:
            self.state[message[0]] = message[1]



        print(self.board_fen())

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


class Connection(object):

    def __init__(self, port_globs, loop):
        self.port_globs = list(port_globs)
        self.loop = loop

        self.serial = None
        self.close()

    def port_candidates(self):
        for port_glob in self.port_globs:
            yield from glob.iglob(port_glob)

    def connect(self):
        for port in self.port_candidates():
            self.connect_port(port)

    def close(self):
        if self.serial is not None:
            self.loop.remove_reader(self.serial)
            self.serial.close()

        self.serial = None
        self.board = Board()
        self.message_id = 0
        self.message_buffer = b""
        self.remaining_message_length = 0

    def connect_port(self, port):
        self.close()

        self.serial = serial.Serial(port,
            stopbits=serial.STOPBITS_ONE,
            parity=serial.PARITY_NONE,
            bytesize=serial.EIGHTBITS)

        self.loop.add_reader(self.serial, self.can_read)
        self.serial.write(bytearray([DGT_SEND_UPDATE_NICE]))
        self.serial.write(bytearray([DGT_SEND_BRD]))

    def can_read(self):
        try:
            if not self.remaining_message_length:
                header = self.serial.read(3) # TODO Ensure this read
                self.message_id = header[0]
                self.remaining_message_length = (header[1] << 7) + header[2] - 3

            message = self.serial.read(self.remaining_message_length)
            self.remaining_message_length -= len(message)
            self.message_buffer += message
        except (TypeError, serial.SerialException):
            self.close()
        else:
            if not self.remaining_message_length:
                self.board.process_message(self.message_id, self.message_buffer)
                self.message_buffer = b""


if __name__ == "__main__":
    loop = asyncio.get_event_loop()

    dgt = Connection(["/dev/ttyACM*"], loop)
    dgt.connect()

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()
