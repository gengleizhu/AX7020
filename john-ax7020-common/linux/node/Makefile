LIB = libjohnhw.so

all: $(LIB)

$(LIB): john_hw.c john_hw.h john_dma_uapi.h
	$(CC) $(CFLAGS) $(LDFLAGS) -Wall -Wextra -O2 -fPIC -shared \
		-Wl,-soname,$(LIB) -o $@ john_hw.c

clean:
	rm -f $(LIB) *.o

.PHONY: all clean
