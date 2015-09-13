asyncdgt: Communicate asynchronously with DGT boards
====================================================

.. image:: https://badge.fury.io/py/asyncdgt.svg
    :target: https://pypi.python.org/pypi/asyncdgt

asyncdgt uses asyncio to communicate asynchronously with a DGT electronic
chess board.

Example
-------

Create an event loop and a connection to the DGT board.

.. code:: python

    import asyncio

    loop = asyncio.get_event_loop()
    dgt = asyncdgt.auto_connect(["/dev/ttyACM*"], loop)

Register some `pyee <https://github.com/jfhbrook/pyee>`_ event handlers. They
will be called whenever a board gets connected, disconnected or the position
changed.

.. code:: python

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

Get some information outside of an event handler using the coroutine
``get_version()``.

.. code:: python

    print("Version:", loop.run_until_complete(dgt.get_version()))


Run the event loop.

.. code:: python

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        dgt.close()
        loop.close()

See ``asyncdgt/__main__.py`` for the complete example. Run with
``python -m asyncdgt /dev/ttyACM0``.

Hardware
--------

Tested with the following boards:

* DGT e-Board 3.1
* DGT e-Board 3.1 Bluetooth

Clocks:

* DGT Clock 3000

Dependencies
------------

* Python 3.4
* `pyee <https://github.com/jfhbrook/pyee>`_
* `pyserial <http://pyserial.sourceforge.net/>`_

``pip install -r requirements.txt``

Related projects
----------------

* `python-chess <https://github.com/niklasf/python-chess>`_,
  a general purpose chess library.

* `picochess <http://www.picochess.org/>`_,
  a standalone chess computer for DGT boards. Some of the DGT protocol handling
  has been shamelessly extracted from their code.

License
-------

python-asyncdtg is licensed under the GPL3. See the ``LICENSE.txt`` file for
the full license text.
