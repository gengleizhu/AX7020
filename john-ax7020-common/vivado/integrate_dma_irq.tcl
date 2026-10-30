# Shared by all five algorithms. No address/data-path changes.
# IRQ_F2P[0] = MM2S, [1] = S2MM, [15:2] = inactive zero.
set_property -dict [list CONFIG.PCW_USE_FABRIC_INTERRUPT {1} \
    CONFIG.PCW_IRQ_F2P_INTR {1} CONFIG.PCW_IRQ_F2P_MODE {DIRECT}] [get_bd_cells ps7_0]
if {[llength [get_bd_cells -quiet dma_irq_concat]]} {
    error "DMA IRQ wiring already exists; refusing duplicate integration"
}
set irq_concat [create_bd_cell -type ip -vlnv xilinx.com:ip:xlconcat:2.1 dma_irq_concat]
set_property -dict [list CONFIG.NUM_PORTS {3} CONFIG.IN0_WIDTH {1} \
    CONFIG.IN1_WIDTH {1} CONFIG.IN2_WIDTH {14}] $irq_concat
set irq_zero [create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:1.1 dma_irq_zero]
set_property -dict [list CONFIG.CONST_WIDTH {14} CONFIG.CONST_VAL {0}] $irq_zero
connect_bd_net [get_bd_pins dma/mm2s_introut] [get_bd_pins dma_irq_concat/In0]
connect_bd_net [get_bd_pins dma/s2mm_introut] [get_bd_pins dma_irq_concat/In1]
connect_bd_net [get_bd_pins dma_irq_zero/dout] [get_bd_pins dma_irq_concat/In2]
connect_bd_net [get_bd_pins dma_irq_concat/dout] [get_bd_pins ps7_0/IRQ_F2P]
foreach pair {{dma/mm2s_introut dma_irq_concat/In0} \
              {dma/s2mm_introut dma_irq_concat/In1} \
              {dma_irq_zero/dout dma_irq_concat/In2} \
              {dma_irq_concat/dout ps7_0/IRQ_F2P}} {
    set a [get_bd_nets -of_objects [get_bd_pins [lindex $pair 0]]]
    set b [get_bd_nets -of_objects [get_bd_pins [lindex $pair 1]]]
    if {[llength $a] != 1 || $a ne $b} {
        error "DMA IRQ connection verification failed: $pair"
    }
}
puts "AX7020_DMA_IRQ_CONNECTED MM2S=IRQ_F2P[format {%s} {[0]}] S2MM=IRQ_F2P[format {%s} {[1]}]"
