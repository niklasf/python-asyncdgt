#!/usr/bin/env python

import asyncio
import serial
import sys

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

    def __init__(self, connection):
        self.connection = connection
        self.state = bytearray(0x00 for _ in range(64))

    def process_message(self, message_id, message):
        print(hex(message_id), message)
        if message_id == DGT_BOARD_DUMP:
            self.state = bytearray(message)
        elif message_id == DGT_MSG_FIELD_UPDATE:
            self.state[message[0]] = message[1]



        print(self.fen())

    def fen(self):
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

    def __init__(self, ports, loop):
        self.ports = ports
        self.loop = loop
        self.board = Board(self)

        self.reconnect = asyncio.Event()

        self.serial = None

        self.message_id = 0
        self.message_buffer = b""
        self.remaining_message_length = 0

        self.serial = serial.Serial(ports,
            stopbits=serial.STOPBITS_ONE,
            parity=serial.PARITY_NONE,
            bytesize=serial.EIGHTBITS)

        self.connected()

    def connected(self):
        loop.add_reader(self.serial, self.can_read)
        self.serial.write(bytearray([DGT_SEND_UPDATE_NICE]))
        self.serial.write(bytearray([DGT_SEND_BRD]))

    def disconnected(self):
        if self.serial is not None:
            self.loop.remove_reader(self.serial)
            self.serial.close()

        self.serial = None
        self.message_id = 0
        self.message_buffer = b""
        self.remaining_message_length = 0

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
            self.disconnected()
        else:
            if not self.remaining_message_length:
                self.board.process_message(self.message_id, self.message_buffer)
                self.message_buffer = b""


if __name__ == "__main__":
    loop = asyncio.get_event_loop()

    dgt = Connection("/dev/ttyACM0", loop)

    loop.run_forever()

    loop.close()
