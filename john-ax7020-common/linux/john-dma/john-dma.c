// SPDX-License-Identifier: GPL-2.0
/* DMAengine client for the common John AXI-Stream shell. */

#include <linux/atomic.h>
#include <linux/completion.h>
#include <linux/dmaengine.h>
#include <linux/dma-mapping.h>
#include <linux/fs.h>
#include <linux/jiffies.h>
#include <linux/miscdevice.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <linux/slab.h>
#include <linux/uaccess.h>

#include "john_dma_uapi.h"

#define JOHN_DMA_NAME   "john-dma"
#define JOHN_DMA_MAX_TX (64U + 65536U)
#define JOHN_DMA_MAX_RX (64U + 8192U)

struct john_dma_dev {
	struct device *dev;
	struct dma_chan *tx_chan;
	struct dma_chan *rx_chan;
	void *tx_buf;
	dma_addr_t tx_dma;
	void *rx_buf;
	dma_addr_t rx_dma;
	size_t tx_len;
	size_t rx_valid;
	struct completion tx_done;
	struct completion rx_done;
	struct mutex lock;
	atomic_t opened;
	atomic64_t tx_completions;
	atomic64_t rx_completions;
	bool running;
	struct miscdevice miscdev;
};

static void john_dma_tx_complete(void *arg)
{
	struct john_dma_dev *jd = arg;

	atomic64_inc(&jd->tx_completions);
	complete(&jd->tx_done);
}

static void john_dma_rx_complete(void *arg)
{
	struct john_dma_dev *jd = arg;

	atomic64_inc(&jd->rx_completions);
	complete(&jd->rx_done);
}

static int john_dma_open(struct inode *inode, struct file *file)
{
	struct miscdevice *misc = file->private_data;
	struct john_dma_dev *jd = container_of(misc, struct john_dma_dev,
						miscdev);

	if (atomic_cmpxchg(&jd->opened, 0, 1))
		return -EBUSY;
	file->private_data = jd;
	return nonseekable_open(inode, file);
}

static int john_dma_release(struct inode *inode, struct file *file)
{
	struct john_dma_dev *jd = file->private_data;

	atomic_set(&jd->opened, 0);
	return 0;
}

static ssize_t john_dma_write(struct file *file, const char __user *buf,
			      size_t count, loff_t *ppos)
{
	struct john_dma_dev *jd = file->private_data;
	ssize_t ret = count;

	if (!count || count > JOHN_DMA_MAX_TX)
		return -EINVAL;

	mutex_lock(&jd->lock);
	if (jd->running) {
		ret = -EBUSY;
		goto out;
	}
	if (copy_from_user(jd->tx_buf, buf, count)) {
		ret = -EFAULT;
		goto out;
	}
	jd->tx_len = count;
	jd->rx_valid = 0;
	*ppos = 0;
out:
	mutex_unlock(&jd->lock);
	return ret;
}

static ssize_t john_dma_read(struct file *file, char __user *buf,
			     size_t count, loff_t *ppos)
{
	struct john_dma_dev *jd = file->private_data;
	ssize_t ret;

	mutex_lock(&jd->lock);
	if (jd->running)
		ret = -EBUSY;
	else
		ret = simple_read_from_buffer(buf, count, ppos, jd->rx_buf,
					      jd->rx_valid);
	mutex_unlock(&jd->lock);
	return ret;
}

static long john_dma_run(struct john_dma_dev *jd, void __user *argp)
{
	struct john_dma_xfer xfer;
	struct dma_async_tx_descriptor *txd = NULL, *rxd = NULL;
	dma_cookie_t tx_cookie = -EINVAL, rx_cookie = -EINVAL;
	unsigned long deadline, left;
	enum dma_status tx_status = DMA_ERROR, rx_status = DMA_ERROR;
	unsigned long dma_flags = DMA_CTRL_ACK | DMA_PREP_INTERRUPT;
	int ret = 0;

	if (copy_from_user(&xfer, argp, sizeof(xfer)))
		return -EFAULT;
	if (xfer.flags || xfer.reserved0 || xfer.reserved1 ||
	    !xfer.tx_len || xfer.tx_len > JOHN_DMA_MAX_TX ||
	    !xfer.rx_len || xfer.rx_len > JOHN_DMA_MAX_RX ||
	    !xfer.timeout_ms || xfer.timeout_ms > 300000)
		return -EINVAL;

	mutex_lock(&jd->lock);
	if (jd->running) {
		ret = -EBUSY;
		goto out_unlock;
	}
	if (xfer.tx_len != jd->tx_len) {
		ret = -EINVAL;
		goto out_unlock;
	}

	jd->running = true;
	jd->rx_valid = 0;
	memset(jd->rx_buf, 0, xfer.rx_len);
	reinit_completion(&jd->tx_done);
	reinit_completion(&jd->rx_done);

	/* The sink must be ready before the source drives the accelerator. */
	rxd = dmaengine_prep_slave_single(jd->rx_chan, jd->rx_dma,
			xfer.rx_len, DMA_DEV_TO_MEM, dma_flags);
	if (!rxd) {
		ret = -EIO;
		goto out_stop;
	}
	rxd->callback = john_dma_rx_complete;
	rxd->callback_param = jd;
	rx_cookie = dmaengine_submit(rxd);
	if (dma_submit_error(rx_cookie)) {
		ret = dma_submit_error(rx_cookie);
		goto out_stop;
	}

	txd = dmaengine_prep_slave_single(jd->tx_chan, jd->tx_dma,
			xfer.tx_len, DMA_MEM_TO_DEV, dma_flags);
	if (!txd) {
		ret = -EIO;
		goto out_stop;
	}
	txd->callback = john_dma_tx_complete;
	txd->callback_param = jd;
	tx_cookie = dmaengine_submit(txd);
	if (dma_submit_error(tx_cookie)) {
		ret = dma_submit_error(tx_cookie);
		goto out_stop;
	}

	dma_async_issue_pending(jd->rx_chan);
	dma_async_issue_pending(jd->tx_chan);
	deadline = jiffies + msecs_to_jiffies(xfer.timeout_ms);

	left = wait_for_completion_timeout(&jd->tx_done,
					   msecs_to_jiffies(xfer.timeout_ms));
	if (!left) {
		ret = -ETIMEDOUT;
		goto out_stop;
	}
	tx_status = dma_async_is_tx_complete(jd->tx_chan, tx_cookie, NULL, NULL);
	if (tx_status != DMA_COMPLETE) {
		ret = -EIO;
		goto out_stop;
	}

	left = time_before(jiffies, deadline) ? deadline - jiffies : 0;
	if (!left || !wait_for_completion_timeout(&jd->rx_done, left)) {
		ret = -ETIMEDOUT;
		goto out_stop;
	}
	rx_status = dma_async_is_tx_complete(jd->rx_chan, rx_cookie, NULL, NULL);
	if (rx_status != DMA_COMPLETE) {
		ret = -EIO;
		goto out_stop;
	}

	jd->rx_valid = xfer.rx_len;
	goto out_report;

out_stop:
	dmaengine_terminate_sync(jd->tx_chan);
	dmaengine_terminate_sync(jd->rx_chan);
	if (tx_cookie >= 0)
		tx_status = dma_async_is_tx_complete(jd->tx_chan, tx_cookie,
						 NULL, NULL);
	if (rx_cookie >= 0)
		rx_status = dma_async_is_tx_complete(jd->rx_chan, rx_cookie,
						 NULL, NULL);
out_report:
	jd->running = false;
	xfer.tx_status = tx_status;
	xfer.rx_status = rx_status;
	if (copy_to_user(argp, &xfer, sizeof(xfer)) && !ret)
		ret = -EFAULT;
out_unlock:
	mutex_unlock(&jd->lock);
	return ret;
}

static long john_dma_ioctl(struct file *file, unsigned int cmd,
			   unsigned long arg)
{
	struct john_dma_dev *jd = file->private_data;
	void __user *argp = (void __user *)arg;
	struct john_dma_info info = {
		.api_version = JOHN_DMA_API_VERSION,
		.max_tx_bytes = JOHN_DMA_MAX_TX,
		.max_rx_bytes = JOHN_DMA_MAX_RX,
	};
	struct john_dma_stats stats;

	switch (cmd) {
	case JOHN_DMA_IOC_RUN:
		return john_dma_run(jd, argp);
	case JOHN_DMA_IOC_INFO:
		return copy_to_user(argp, &info, sizeof(info)) ? -EFAULT : 0;
	case JOHN_DMA_IOC_STATS:
		memset(&stats, 0, sizeof(stats));
		stats.tx_completions = atomic64_read(&jd->tx_completions);
		stats.rx_completions = atomic64_read(&jd->rx_completions);
		stats.running = jd->running;
		return copy_to_user(argp, &stats, sizeof(stats)) ? -EFAULT : 0;
	default:
		return -ENOTTY;
	}
}

static const struct file_operations john_dma_fops = {
	.owner = THIS_MODULE,
	.open = john_dma_open,
	.release = john_dma_release,
	.read = john_dma_read,
	.write = john_dma_write,
	.unlocked_ioctl = john_dma_ioctl,
	.llseek = no_llseek,
};

static int john_dma_probe(struct platform_device *pdev)
{
	struct john_dma_dev *jd;
	int ret;

	jd = devm_kzalloc(&pdev->dev, sizeof(*jd), GFP_KERNEL);
	if (!jd)
		return -ENOMEM;
	jd->dev = &pdev->dev;
	mutex_init(&jd->lock);
	init_completion(&jd->tx_done);
	init_completion(&jd->rx_done);
	atomic_set(&jd->opened, 0);
	atomic64_set(&jd->tx_completions, 0);
	atomic64_set(&jd->rx_completions, 0);

	ret = dma_set_mask_and_coherent(&pdev->dev, DMA_BIT_MASK(32));
	if (ret) {
		dev_err(&pdev->dev, "32-bit DMA mask unavailable: %d\n", ret);
		return ret;
	}

	jd->tx_chan = dma_request_chan(&pdev->dev, "tx");
	if (IS_ERR(jd->tx_chan)) {
		ret = PTR_ERR(jd->tx_chan);
		if (ret != -EPROBE_DEFER)
			dev_err(&pdev->dev, "cannot request MM2S channel: %d\n", ret);
		return ret;
	}
	jd->rx_chan = dma_request_chan(&pdev->dev, "rx");
	if (IS_ERR(jd->rx_chan)) {
		ret = PTR_ERR(jd->rx_chan);
		if (ret != -EPROBE_DEFER)
			dev_err(&pdev->dev, "cannot request S2MM channel: %d\n", ret);
		goto err_release_tx;
	}

	jd->tx_buf = dma_alloc_coherent(&pdev->dev, JOHN_DMA_MAX_TX,
					&jd->tx_dma, GFP_KERNEL);
	if (!jd->tx_buf) {
		ret = -ENOMEM;
		goto err_release_rx;
	}
	jd->rx_buf = dma_alloc_coherent(&pdev->dev, JOHN_DMA_MAX_RX,
					&jd->rx_dma, GFP_KERNEL);
	if (!jd->rx_buf) {
		ret = -ENOMEM;
		goto err_free_tx;
	}

	jd->miscdev.minor = MISC_DYNAMIC_MINOR;
	jd->miscdev.name = JOHN_DMA_NAME;
	jd->miscdev.fops = &john_dma_fops;
	jd->miscdev.parent = &pdev->dev;
	ret = misc_register(&jd->miscdev);
	if (ret)
		goto err_free_rx;

	platform_set_drvdata(pdev, jd);
	dev_info(&pdev->dev, "ready: %s, tx=%s rx=%s, max=%u/%u bytes\n",
		 jd->miscdev.name, dma_chan_name(jd->tx_chan),
		 dma_chan_name(jd->rx_chan), JOHN_DMA_MAX_TX, JOHN_DMA_MAX_RX);
	return 0;

err_free_rx:
	dma_free_coherent(&pdev->dev, JOHN_DMA_MAX_RX, jd->rx_buf, jd->rx_dma);
err_free_tx:
	dma_free_coherent(&pdev->dev, JOHN_DMA_MAX_TX, jd->tx_buf, jd->tx_dma);
err_release_rx:
	dma_release_channel(jd->rx_chan);
err_release_tx:
	dma_release_channel(jd->tx_chan);
	return ret;
}

static int john_dma_remove(struct platform_device *pdev)
{
	struct john_dma_dev *jd = platform_get_drvdata(pdev);

	misc_deregister(&jd->miscdev);
	dmaengine_terminate_sync(jd->tx_chan);
	dmaengine_terminate_sync(jd->rx_chan);
	dma_free_coherent(&pdev->dev, JOHN_DMA_MAX_RX, jd->rx_buf, jd->rx_dma);
	dma_free_coherent(&pdev->dev, JOHN_DMA_MAX_TX, jd->tx_buf, jd->tx_dma);
	dma_release_channel(jd->rx_chan);
	dma_release_channel(jd->tx_chan);
	return 0;
}

static const struct of_device_id john_dma_of_match[] = {
	{ .compatible = "john,axi-dma-client-1.0" },
	{ }
};
MODULE_DEVICE_TABLE(of, john_dma_of_match);

static struct platform_driver john_dma_driver = {
	.probe = john_dma_probe,
	.remove = john_dma_remove,
	.driver = {
		.name = JOHN_DMA_NAME,
		.of_match_table = john_dma_of_match,
	},
};
module_platform_driver(john_dma_driver);

MODULE_AUTHOR("AX7020 John project");
MODULE_DESCRIPTION("DMAengine client for John AXI-Stream accelerator shells");
MODULE_LICENSE("GPL v2");
