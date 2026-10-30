SUMMARY = "Persistent UDP service for John FPGA accelerator nodes"
SECTION = "PETALINUX/apps"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = "file://john_node_service.py \
           file://john_udp_protocol.py \
           file://S95john-node \
           file://john_hw.c \
           file://john_hw.h \
           file://john_dma_uapi.h \
           file://Makefile \
          "

S = "${WORKDIR}"

inherit update-rc.d

# libjohnhw.so is loaded directly by ctypes at runtime; it is not an unversioned
# development linker stub.
SOLIBS = ".so"
FILES_SOLIBSDEV = ""

INITSCRIPT_NAME = "john-node"
INITSCRIPT_PARAMS = "defaults 95"

RDEPENDS_${PN} += "python3-core python3-compression python3-ctypes python3-logging \
                   python3-netclient python3-threading"

do_compile() {
	oe_runmake
}

do_install() {
	install -d ${D}${sbindir}
	install -m 0755 ${WORKDIR}/john_node_service.py ${D}${sbindir}/john-node
	install -m 0644 ${WORKDIR}/john_udp_protocol.py ${D}${sbindir}/john_udp_protocol.py
	install -d ${D}${libdir}
	install -m 0755 ${WORKDIR}/libjohnhw.so ${D}${libdir}/libjohnhw.so
	install -d ${D}${sysconfdir}/init.d
	install -m 0755 ${WORKDIR}/S95john-node ${D}${sysconfdir}/init.d/john-node
}

FILES_${PN} += "${sysconfdir}/init.d/john-node ${libdir}/libjohnhw.so"
