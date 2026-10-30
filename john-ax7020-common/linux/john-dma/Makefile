obj-m := john-dma.o

all:
	$(MAKE) -C $(KERNEL_SRC) M=$(CURDIR)

modules_install:
	$(MAKE) -C $(KERNEL_SRC) M=$(CURDIR) modules_install

clean:
	rm -f *.o *~ core .depend .*.cmd *.ko *.mod.c
	rm -f Module.markers Module.symvers modules.order
	rm -rf .tmp_versions Modules.symvers

.PHONY: all modules_install clean
