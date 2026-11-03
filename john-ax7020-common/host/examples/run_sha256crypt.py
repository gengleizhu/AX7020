#!/usr/bin/env python3
from example_common import parser, run

TARGET = "$5$rounds=1000$salt1234$aMT3fONWDA1J3Ndh7sjwgpNo6J/43lD0riI3tf2YYh2"

if __name__ == "__main__":
    args = parser("Run one real SHA256-crypt FPGA batch").parse_args()
    run(args, "sha256crypt", ["bad", "password", "123456"], TARGET)
