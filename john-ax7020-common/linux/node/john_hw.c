// SPDX-License-Identifier: MIT
/* Safe aligned AXI-Lite and /dev/john-dma access for the Python node service. */

#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <unistd.h>

#include "john_dma_uapi.h"
#include "john_hw.h"

#define REG_BASE 0x43c00000UL
#define REG_SIZE 0x10000UL
#define REG32(hw, off) (*(volatile uint32_t *)((uint8_t *)(hw)->regs + (off)))
#define REGISTER_MAGIC 0x4a435250U
#define REGISTER_ABI 0x00010001U
#define STREAM_MAGIC 0x3151544aU
#define STREAM_ABI 0x00010000U

struct john_hw {
	int mem_fd;
	int dma_fd;
	void *regs;
	uint32_t max_tx;
	uint32_t max_rx;
};

static void set_error(char *error, size_t size, const char *format, ...)
{
	va_list args;

	if (!error || !size)
		return;
	va_start(args, format);
	vsnprintf(error, size, format, args);
	va_end(args);
}

static int command(struct john_hw *hw, uint32_t value,
		   char *error, size_t error_size)
{
	uint32_t sequence = REG32(hw, 0x088) + 1;
	unsigned int i;

	REG32(hw, 0x088) = sequence;
	__sync_synchronize();
	REG32(hw, 0x080) = value;
	for (i = 0; i < 1000; ++i) {
		if (REG32(hw, 0x08c) == sequence) {
			uint32_t result = REG32(hw, 0x090);
			if (result) {
				set_error(error, error_size,
					  "PL command %u rejected: %u", value, result);
				return -1;
			}
			return 0;
		}
		usleep(100);
	}
	set_error(error, error_size, "PL command %u acknowledgement timeout", value);
	return -1;
}

void *john_hw_open(const char *dma_path, char *error, size_t error_size)
{
	struct john_dma_info info;
	struct john_hw *hw = calloc(1, sizeof(*hw));

	if (!hw) {
		set_error(error, error_size, "calloc: %s", strerror(errno));
		return NULL;
	}
	hw->mem_fd = -1;
	hw->dma_fd = -1;
	hw->regs = MAP_FAILED;
	hw->mem_fd = open("/dev/mem", O_RDWR | O_SYNC);
	if (hw->mem_fd < 0) {
		set_error(error, error_size, "open /dev/mem: %s", strerror(errno));
		goto fail;
	}
	hw->regs = mmap(NULL, REG_SIZE, PROT_READ | PROT_WRITE, MAP_SHARED,
			hw->mem_fd, REG_BASE);
	if (hw->regs == MAP_FAILED) {
		set_error(error, error_size, "mmap registers: %s", strerror(errno));
		goto fail;
	}
	hw->dma_fd = open(dma_path ? dma_path : "/dev/john-dma", O_RDWR);
	if (hw->dma_fd < 0) {
		set_error(error, error_size, "open john-dma: %s", strerror(errno));
		goto fail;
	}
	memset(&info, 0, sizeof(info));
	if (ioctl(hw->dma_fd, JOHN_DMA_IOC_INFO, &info)) {
		set_error(error, error_size, "JOHN_DMA_IOC_INFO: %s", strerror(errno));
		goto fail;
	}
	if (info.api_version != JOHN_DMA_API_VERSION || info.reserved) {
		set_error(error, error_size, "john-dma API mismatch");
		goto fail;
	}
	hw->max_tx = info.max_tx_bytes;
	hw->max_rx = info.max_rx_bytes;
	if (REG32(hw, 0x000) != REGISTER_MAGIC ||
	    REG32(hw, 0x004) != REGISTER_ABI) {
		set_error(error, error_size, "PL register ABI mismatch");
		goto fail;
	}
	return hw;

fail:
	john_hw_close(hw);
	return NULL;
}

void john_hw_close(void *handle)
{
	struct john_hw *hw = handle;

	if (!hw)
		return;
	if (hw->dma_fd >= 0)
		close(hw->dma_fd);
	if (hw->regs != MAP_FAILED)
		munmap(hw->regs, REG_SIZE);
	if (hw->mem_fd >= 0)
		close(hw->mem_fd);
	free(hw);
}

int john_hw_identify(void *handle, struct john_hw_identity *identity,
		     char *error, size_t error_size)
{
	struct john_hw *hw = handle;

	if (!hw || !identity) {
		set_error(error, error_size, "invalid hardware handle");
		return -1;
	}
	if (REG32(hw, 0x000) != REGISTER_MAGIC ||
	    REG32(hw, 0x004) != REGISTER_ABI) {
		set_error(error, error_size, "PL register ABI mismatch");
		return -1;
	}
	identity->algorithm = REG32(hw, 0x020);
	identity->units = REG32(hw, 0x024);
	identity->cores = REG32(hw, 0x028);
	identity->clock_hz = REG32(hw, 0x05c);
	identity->capabilities = REG32(hw, 0x030);
	identity->status = REG32(hw, 0x084);
	identity->build_date = REG32(hw, 0x010);
	identity->register_abi = REG32(hw, 0x004);
	identity->stream_abi = REG32(hw, 0x00c);
	identity->native_status = REG32(hw, 0x070);
	return 0;
}

int john_hw_dma_stats(void *handle, struct john_hw_dma_stats *stats,
		      char *error, size_t error_size)
{
	struct john_hw *hw = handle;
	struct john_dma_stats kernel_stats;

	if (!hw || !stats) {
		set_error(error, error_size, "invalid hardware handle");
		return -1;
	}
	memset(&kernel_stats, 0, sizeof(kernel_stats));
	if (ioctl(hw->dma_fd, JOHN_DMA_IOC_STATS, &kernel_stats)) {
		set_error(error, error_size, "JOHN_DMA_IOC_STATS: %s", strerror(errno));
		return -1;
	}
	stats->tx_completions = kernel_stats.tx_completions;
	stats->rx_completions = kernel_stats.rx_completions;
	stats->running = kernel_stats.running;
	stats->reserved = 0;
	return 0;
}

int john_hw_run(void *handle, const void *request_buffer, uint32_t request_len,
		void *response, uint32_t response_capacity,
		uint32_t *response_len, uint32_t timeout_ms,
		struct john_hw_metrics *metrics, char *error, size_t error_size)
{
	struct john_hw *hw = handle;
	const uint32_t *header = request_buffer;
	struct john_hw_identity identity;
	struct john_dma_xfer xfer;
	uint32_t descriptor[18] = {0};
	uint32_t expected_response, status;
	uint8_t *out = response;
	ssize_t count;
	size_t done = 0;
	unsigned int i;
	int armed = 0;

	if (!hw || !request_buffer || !response || !response_len || !metrics ||
	    request_len < 64 || request_len > hw->max_tx) {
		set_error(error, error_size, "invalid run arguments");
		return -1;
	}
	if (header[0] != STREAM_MAGIC || header[1] != STREAM_ABI ||
	    header[2] != 64 || header[3] != request_len || header[14] || header[15]) {
		set_error(error, error_size, "invalid common request header");
		return -1;
	}
	expected_response = 64 + header[12];
	if (expected_response > hw->max_rx || expected_response > response_capacity) {
		set_error(error, error_size, "response capacity too small");
		return -1;
	}
	if (john_hw_identify(hw, &identity, error, error_size))
		return -1;
	if (header[4] != identity.algorithm) {
		set_error(error, error_size, "request algorithm does not match bitstream");
		return -1;
	}
	if (!(identity.status & 1) || (identity.status & 0x2e)) {
		set_error(error, error_size, "PL not ready: status=0x%08x",
			  identity.status);
		return -1;
	}

	count = write(hw->dma_fd, request_buffer, request_len);
	if (count != (ssize_t)request_len) {
		set_error(error, error_size, "write john-dma: %s", strerror(errno));
		return -1;
	}

	descriptor[0] = header[6];
	descriptor[1] = header[7];
	descriptor[2] = header[8];
	descriptor[3] = header[9];
	descriptor[4] = header[4];
	descriptor[5] = header[5];
	descriptor[6] = header[3] - 64;
	descriptor[7] = expected_response;
	descriptor[8] = header[10];
	descriptor[9] = header[11];
	descriptor[10] = header[12];
	descriptor[11] = header[13];
	for (i = 0; i < 18; ++i)
		REG32(hw, 0x100 + 4 * i) = descriptor[i];
	__sync_synchronize();
	if (command(hw, 1, error, error_size))
		return -1;
	armed = 1;

	memset(&xfer, 0, sizeof(xfer));
	xfer.tx_len = request_len;
	xfer.rx_len = expected_response;
	xfer.timeout_ms = timeout_ms;
	if (ioctl(hw->dma_fd, JOHN_DMA_IOC_RUN, &xfer)) {
		set_error(error, error_size,
			  "DMA run: %s tx=%d rx=%d PL=0x%08x error=%u detail=%u",
			  strerror(errno), xfer.tx_status, xfer.rx_status,
			  REG32(hw, 0x084), REG32(hw, 0x09c), REG32(hw, 0x0a0));
		goto fail;
	}
	while (done < expected_response) {
		count = read(hw->dma_fd, out + done, expected_response - done);
		if (count <= 0) {
			set_error(error, error_size, "read john-dma: %s", strerror(errno));
			goto fail;
		}
		done += (size_t)count;
	}
	status = REG32(hw, 0x084);
	if (!(status & 4) || (status & 8)) {
		set_error(error, error_size,
			  "PL failed: status=0x%08x error=%u detail=%u", status,
			  REG32(hw, 0x09c), REG32(hw, 0x0a0));
		goto fail;
	}
	if (command(hw, 4, error, error_size))
		goto fail;
	metrics->completed_lo = REG32(hw, 0x188);
	metrics->completed_hi = REG32(hw, 0x18c);
	metrics->cycles_lo = REG32(hw, 0x1a8);
	metrics->cycles_hi = REG32(hw, 0x1ac);
	metrics->status = status;
	if (command(hw, 2, error, error_size))
		goto fail;
	armed = 0;
	*response_len = expected_response;
	return 0;

fail:
	if (armed) {
		size_t used = error && error_size ? strlen(error) : 0;
		if (error && used + 40 < error_size)
			snprintf(error + used, error_size - used,
				 "; PL remains armed; inspect NEED_RELOAD");
	}
	return -1;
}
