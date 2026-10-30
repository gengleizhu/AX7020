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
mkdir -p "$module/files" "$app/files"

cp "$here/petalinux/recipes-modules/john-dma/john-dma.bb" "$module/"
cp "$here/john-dma/john-dma.c" "$module/files/"
cp "$here/john-dma/Makefile" "$module/files/"
cp "$here/include/john_dma_uapi.h" "$module/files/"

cp "$here/petalinux/recipes-apps/john-node/john-node.bb" "$app/"
cp "$here/node/john_node_service.py" "$app/files/"
cp "$here/node/john_udp_protocol.py" "$app/files/"
cp "$here/node/john_health.py" "$app/files/"
cp "$here/node/S95john-node" "$app/files/"
cp "$here/node/john_hw.c" "$app/files/"
cp "$here/node/john_hw.h" "$app/files/"
cp "$here/node/Makefile" "$app/files/"
cp "$here/include/john_dma_uapi.h" "$app/files/"

echo "Copied john-dma and john-node sources into $project"
echo "Merge petalinux/device-tree/john-dma-client.dtsi into system-user.dtsi."
echo "Then enable CONFIG_john-dma and CONFIG_john-node in rootfs_config."
