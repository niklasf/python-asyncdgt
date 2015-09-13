#!/usr/bin/env python
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

import asyncdgt
import unittest


class BoardTestCase(unittest.TestCase):
    def test_board_fen(self):
        board = asyncdgt.Board()
        self.assertEqual(board.board_fen(), "8/8/8/8/8/8/8/8")

        fen = "2k3nr/ppp1bpp1/8/4n3/2Pr4/5NPq/PP1BPP1P/R2Q1RK1"
        board.set_board_fen(fen)
        self.assertEqual(board.board_fen(), fen)


if __name__ == "__main__":
    unittest.main()
