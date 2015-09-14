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
  python -m asyncdgt <dgt-port>

<dgt-port>
  The serial port with the DGT board.
"""

import asyncio
import asyncdgt
import logging
import sys
import serial
import serial.tools.list_ports


logging.basicConfig(level=logging.DEBUG)


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

    dgt = asyncdgt.auto_connect(port_globs, loop)

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
        print()

    @dgt.on("button_pressed")
    def on_button_pressed(button):
        print("Button {0} pressed!".format(button))

    # Get some information.
    print("Version:", loop.run_until_complete((dgt.get_version())))
    print("Serial:", loop.run_until_complete(dgt.get_serialnr()))
    print("Long serial:", loop.run_until_complete(dgt.get_long_serialnr()))
    print("Board:", loop.run_until_complete(dgt.get_board()).board_fen())
    print("Battery status:", loop.run_until_complete(dgt.get_battery_status()))
    print("Clock version:", loop.run_until_complete(dgt.get_clock_version()))

    print("Beeping ...")
    loop.run_until_complete(dgt.clock_beep(0.1))

    # Run the event loop.
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


if __name__ == "__main__":
    port_globs = sys.argv[1:]
    if not port_globs:
        sys.exit(usage())
    else:
        sys.exit(main(port_globs))
