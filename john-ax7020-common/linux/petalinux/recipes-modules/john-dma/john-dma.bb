SUMMARY = "DMAengine client for John AXI-Stream accelerator shells"
SECTION = "PETALINUX/modules"
LICENSE = "GPLv2"
LIC_FILES_CHKSUM = "file://john-dma.c;beginline=1;endline=1;md5=50d2ba0afecd20f74c12a4bdbcfcfe61"

inherit module

SRC_URI = "file://Makefile \
           file://john-dma.c \
           file://john_dma_uapi.h \
          "

S = "${WORKDIR}"

KERNEL_MODULE_AUTOLOAD += "john-dma"
