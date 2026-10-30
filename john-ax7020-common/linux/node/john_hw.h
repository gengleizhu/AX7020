#ifndef JOHN_HW_H
#define JOHN_HW_H

#include <stddef.h>
#include <stdint.h>

struct john_hw_identity {
	uint32_t algorithm;
	uint32_t units;
	uint32_t cores;
	uint32_t clock_hz;
	uint32_t capabilities;
	uint32_t status;
};

struct john_hw_metrics {
	uint32_t completed_lo;
	uint32_t completed_hi;
	uint32_t cycles_lo;
	uint32_t cycles_hi;
	uint32_t status;
};

void *john_hw_open(const char *dma_path, char *error, size_t error_size);
void john_hw_close(void *handle);
int john_hw_identify(void *handle, struct john_hw_identity *identity,
		     char *error, size_t error_size);
int john_hw_run(void *handle, const void *request, uint32_t request_len,
		void *response, uint32_t response_capacity,
		uint32_t *response_len, uint32_t timeout_ms,
		struct john_hw_metrics *metrics, char *error, size_t error_size);

#endif
