import asyncio
import asyncdgt
import logging
import sys

port_globs = sys.argv[1:]
if not port_globs:
    print("Usage: python -m asyncdgt <dgt-port>")
    print("  for example /dev/ttyACM0")
    sys.exit(1)

logging.basicConfig(level=logging.DEBUG)

loop = asyncio.get_event_loop()

dgt = asyncdgt.auto_connect(sys.argv[1:], loop)

@dgt.on("connected")
def on_connected(port):
    print("Connected to {0}!".format(port))
    #print("Version:", loop.run_until_complete(dgt.get_version()))
    #print("Serial:", loop.run_until_complete(dgt.get_serialnr()))
    #print("Long serial:", loop.run_until_complete(dgt.get_long_serialnr()))
    #print("Board:", loop.run_until_complete(dgt.get_board()))
    #print("Battery status:", loop.run_until_complete(dgt.get_battery_status()))

@dgt.on("disconnected")
def on_disconnected():
    print("Disconnected!")

@dgt.on("board")
def on_board(board):
    print("FEN: {0}".format(board.board_fen()))

try:
    loop.run_forever()
except KeyboardInterrupt:
    pass
finally:
    dgt.close()

    pending = asyncio.Task.all_tasks(loop)
    loop.run_until_complete(asyncio.gather(*pending))
    loop.close()
