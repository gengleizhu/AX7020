#!/usr/bin/env python3
from example_common import parser, run

TARGET = "..X8NBuQ4l6uQ"

if __name__ == "__main__":
    args = parser("Run one real DES-crypt FPGA batch").parse_args()
    run(args, "descrypt", ["bad", "password", ""], TARGET)
