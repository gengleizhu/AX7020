#!/usr/bin/env python3
from example_common import parser, run

TARGET = "$2a$04$pIqNJ/d3.iUtNb........1ynmOuHkBNwBW8zbBj6wTB8XX4/HPiy"

if __name__ == "__main__":
    args = parser("Run one real bcrypt FPGA batch").parse_args()
    run(args, "bcrypt", ["bad", "01234567", "password"], TARGET)
