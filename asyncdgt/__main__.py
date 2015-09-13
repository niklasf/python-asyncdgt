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

dgt = asyncdgt.Connection(sys.argv[1:], loop)

@dgt.on("connected")
def on_connect(dgt, port):
    print("Connected to {0}!".format(port))

@dgt.on("disconnected")
def on_disconnect(dgt):
    print("Disconnected!".format(port))

@dgt.on("board")
def on_board(dgt, board):
    print("FEN: {0}".format(board.board_fen()))

dgt.connect()

try:
    loop.run_forever()
except KeyboardInterrupt:
    pass
finally:
    dgt.close()
    loop.close()
