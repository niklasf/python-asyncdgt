# -*- coding: utf-8 -*-
# This file is part of the python-asyncdgt library.
# Copyright (C) 2015 Niklas Fiekas <niklas.fiekas@tu-clausthal.de>
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
The asyncdgt library.
Copyright (C) 2015 Niklas Fiekas <niklas.fiekas@tu-clausthal.de>

Usage:
  python -m asyncdgt [--debug] <dgt-port>

[--debug]
  Enable debug logger.

<dgt-port>
  The serial port with the DGT board.
"""

import asyncio
import asyncdgt
import logging
import sys
import serial
import serial.tools.list_ports




def usage():
    # Print usage information.
    print(__doc__.strip())

    # List the available ports.
    print("  Probably one of:")
    for dev, name, info in serial.tools.list_ports.comports():
        print("  * {0} ({1})".format(dev, info))

    return 1


def main(port_globs):
    loop = asyncio.get_event_loop()

    dgt = asyncdgt.auto_connect(loop, port_globs)

    @dgt.on("connected")
    def on_connected(port):
        print("Board connected to {0}!".format(port))

    @dgt.on("disconnected")
    def on_disconnected():
        print("Board disconnected!")

    @dgt.on("board")
    def on_board(board):
        print("Position changed:")
        print(board)

    @dgt.on("button_pressed")
    def on_button_pressed(button):
        print("Button {0} pressed!".format(button))

    @dgt.on("clock")
    def on_clock(clock):
        print("Clock status changed:", clock)

    # Get some information.
    print("Version:", loop.run_until_complete(dgt.get_version()))
    print("Serial:", loop.run_until_complete(dgt.get_serialnr()))
    print("Long serial:", loop.run_until_complete(dgt.get_long_serialnr()))
    print("Board:", loop.run_until_complete(dgt.get_board()).board_fen())

    # Get the clock version.
    try:
        print("Clock version:", loop.run_until_complete(asyncio.wait_for(dgt.get_clock_version(), 1.0)))
    except asyncio.TimeoutError:
        print("Clock version request timed out.")

    # Display some text.
    print("Displaying text ...")
    quote = "Now, I am become death, the destroyer of worlds. Ready"
    loop.run_until_complete(clock_display_sentence(dgt, quote))

    # Let the clock beep
    try:
        print("Beep ...")
        loop.run_until_complete(asyncio.wait_for(dgt.clock_beep(0.1), 1.0))
    except asyncio.TimeoutError:
        print("Beep not acknowledged in time.")

    # Run the event loop.
    print("Running event loop ...")
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        dgt.close()

        pending = asyncio.Task.all_tasks(loop)
        loop.run_until_complete(asyncio.gather(*pending))
        loop.close()

    return 0

@asyncio.coroutine
def clock_display_sentence(dgt, sentence):
    for word in sentence.split():
        yield from asyncio.sleep(0.2)

        try:
            yield from asyncio.wait_for(dgt.clock_text(word), 0.5)
        except asyncio.TimeoutError:
            print("Sending clock text timed out.")

if __name__ == "__main__":
    if "--debug" in sys.argv:
        logging.basicConfig(level=logging.DEBUG)

    port_globs = [arg for arg in sys.argv[1:] if arg != "--debug"]
    if not port_globs:
        sys.exit(usage())
    else:
        sys.exit(main(port_globs))
