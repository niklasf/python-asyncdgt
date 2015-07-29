#!/usr/bin/env python

import asyncio
import serial

DGT_SEND_BRD = 0x42

DGT_BOARD_DUMP = 0x86


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
    0x00: "."
}


class Connection(object):

    def __init__(self, port, loop):
        self.loop = loop

        self.serial = serial.Serial(port,
            stopbits=serial.STOPBITS_ONE,
            parity=serial.PARITY_NONE,
            bytesize=serial.EIGHTBITS)

        loop.add_reader(self.serial, self.can_read)

        self.serial.write(bytearray([DGT_SEND_BRD]))

    def process_board_dump(self, message):
        fen = []
        empty = 0

        for index, c in enumerate(message):
            if not c:
                empty += 1

            if empty > 0:
                if c or (index + 1) % 8 == 0:
                    fen.append(str(empty))
                    empty = 0

            if c:
                fen.append(PIECE_TO_CHAR[c])

            if (index + 1) % 8 == 0 and index < 63:
                fen.append("/")

        print("".join(fen))

    def can_read(self):
        header = self.serial.read(3)
        message_id = header[0]
        message_length = (header[1] << 7) + header[2] - 3
        message = self.serial.read(message_length)

        print(message_id, message)

        if message_id == DGT_BOARD_DUMP:
            self.process_board_dump(message)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()

    dgt = Connection("/dev/ttyACM0", loop)

    loop.run_forever()

    loop.close()
