#!/usr/bin/env python3
from example_common import parser, run

TARGET = "$6$rounds=1000$salt1234$SVDFHbJXYrzjGi2fA1k3ws01/D9q0ZTAh1KfRF5.ehgjVBqfHUaKqfynXefJ4DxIWxkMAITYq9mmcBl938YQ//"

if __name__ == "__main__":
    args = parser("Run one real SHA512-crypt FPGA batch").parse_args()
    run(args, "sha512crypt", ["bad", "password", "123456"], TARGET)
