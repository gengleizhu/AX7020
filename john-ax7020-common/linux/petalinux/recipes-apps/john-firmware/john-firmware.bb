SUMMARY = "AX7020 John FPGA algorithm firmware and manifests"
SECTION = "PETALINUX/apps"
LICENSE = "CLOSED"

SRC_URI = "file://john_ax7020_bcrypt8.bit.bin \
           file://john_ax7020_descrypt8.bit.bin \
           file://john_ax7020_md5crypt8.bit.bin \
           file://john_ax7020_sha256crypt8.bit.bin \
           file://john_ax7020_sha512crypt4.bit.bin \
           file://john_ax7020_bcrypt8.json \
           file://john_ax7020_descrypt8.json \
           file://john_ax7020_md5crypt8.json \
           file://john_ax7020_sha256crypt8.json \
           file://john_ax7020_sha512crypt4.json \
          "

S = "${WORKDIR}"

do_install() {
	install -d ${D}${nonarch_base_libdir}/firmware
	install -m 0644 ${WORKDIR}/john_ax7020_*.bit.bin ${D}${nonarch_base_libdir}/firmware/
	install -d ${D}${sysconfdir}/john/bitstreams
	install -m 0644 ${WORKDIR}/john_ax7020_*.json ${D}${sysconfdir}/john/bitstreams/
}

FILES_${PN} += "${nonarch_base_libdir}/firmware/john_ax7020_*.bit.bin \
                ${sysconfdir}/john/bitstreams/john_ax7020_*.json"

