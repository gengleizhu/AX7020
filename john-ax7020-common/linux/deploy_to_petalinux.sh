#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 /path/to/petalinux/project" >&2
    exit 2
fi

project=$(cd "$1" && pwd)
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
meta="$project/project-spec/meta-user"

test -d "$meta" || {
    echo "Not a PetaLinux project: $project" >&2
    exit 2
}

module="$meta/recipes-modules/john-dma"
app="$meta/recipes-apps/john-node"
firmware="$meta/recipes-apps/john-firmware"
firmware_source="$here/../build/linux_firmware"
user_rootfs="$meta/conf/user-rootfsconfig"
mkdir -p "$module/files" "$app/files" "$firmware/files"

cp "$here/petalinux/recipes-modules/john-dma/john-dma.bb" "$module/"
cp "$here/john-dma/john-dma.c" "$module/files/"
cp "$here/john-dma/Makefile" "$module/files/"
cp "$here/include/john_dma_uapi.h" "$module/files/"

cp "$here/petalinux/recipes-apps/john-node/john-node.bb" "$app/"
cp "$here/node/john_node_service.py" "$app/files/"
cp "$here/node/john_udp_protocol.py" "$app/files/"
cp "$here/node/john_health.py" "$app/files/"
cp "$here/node/john_bitstream.py" "$app/files/"
cp "$here/node/john_manage_service.py" "$app/files/"
cp "$here/node/john_management.py" "$app/files/"
cp "$here/node/S94john-manage" "$app/files/"
cp "$here/node/john-ssh-restore" "$app/files/"
cp "$here/node/S95john-node" "$app/files/"
cp "$here/node/john_hw.c" "$app/files/"
cp "$here/node/john_hw.h" "$app/files/"
cp "$here/node/Makefile" "$app/files/"
cp "$here/include/john_dma_uapi.h" "$app/files/"

cp "$here/petalinux/recipes-apps/john-firmware/john-firmware.bb" "$firmware/"
for name in bcrypt8 descrypt8 md5crypt8 sha256crypt8 sha512crypt4; do
    cp "$firmware_source/john_ax7020_${name}.bit.bin" "$firmware/files/"
    cp "$firmware_source/john_ax7020_${name}.json" "$firmware/files/"
done
grep -qx 'CONFIG_john-firmware' "$user_rootfs" || printf '\nCONFIG_john-firmware\n' >> "$user_rootfs"

echo "Copied john-dma, john-node and five FPGA firmware images into $project"
echo "Merge petalinux/device-tree/john-dma-client.dtsi into system-user.dtsi."
echo "Then enable CONFIG_john-dma, CONFIG_john-node and CONFIG_john-firmware in rootfs_config."
