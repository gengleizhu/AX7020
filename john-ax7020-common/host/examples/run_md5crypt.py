#!/usr/bin/env python3
from example_common import parser, run

TARGET = "$1$salt1234$HJCsv4hSeVLHo3hVyl4nh0"

if __name__ == "__main__":
    args = parser("Run one real MD5-crypt FPGA batch").parse_args()
    run(args, "md5crypt", ["bad", "password", "123456"], TARGET)

