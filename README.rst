asyncdgt: Communicate asynchronously with DGT boards
====================================================

.. image:: https://badge.fury.io/py/asyncdgt
    :target: https://pypi.python.org/pypi/asyncdgt

asyncdgt uses asyncio to communicate asynchronously with a DGT electronic
chess boards.

Example
-------

See ``asyncdgt/__main__.py`` for an example. Run with
``python -m asyncdgt /dev/ttyACM0``.

Hardware
--------

TODO: Tested with ...

Dependencies
------------

* Python 3.4
* [pyee](https://github.com/jfhbrook/pyee)
* [pyserial](http://pyserial.sourceforge.net/)

``pip install -r requirements.txt``

Related projects
----------------

* [python-chess](https://github.com/niklasf/python-chess),
  a general purpose chess library

* [picochess](http://www.picochess.org/),
  a standalone chess computer for DGT boards

License
-------

python-asyncdtg is licensed under the GPL3. See the LICENSE.txt file for the
full copyright and license information.
