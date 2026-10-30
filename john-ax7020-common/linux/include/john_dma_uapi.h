#ifndef JOHN_DMA_UAPI_H
#define JOHN_DMA_UAPI_H

#include <linux/ioctl.h>
#include <linux/types.h>

#define JOHN_DMA_API_VERSION 0x00010000U
#define JOHN_DMA_IOC_MAGIC   'J'

struct john_dma_xfer {
	__u32 tx_len;
	__u32 rx_len;
	__u32 timeout_ms;
	__u32 flags;
	__s32 tx_status;
	__s32 rx_status;
	__u32 reserved0;
	__u32 reserved1;
};

struct john_dma_info {
	__u32 api_version;
	__u32 max_tx_bytes;
	__u32 max_rx_bytes;
	__u32 reserved;
};

#define JOHN_DMA_IOC_RUN  _IOWR(JOHN_DMA_IOC_MAGIC, 1, struct john_dma_xfer)
#define JOHN_DMA_IOC_INFO _IOR(JOHN_DMA_IOC_MAGIC, 2, struct john_dma_info)

#endif
