# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge
from cocotb.triggers import ClockCycles
from cocotb.types import Logic
from cocotb.types import LogicArray

async def await_half_sclk(dut):
    """Wait for the SCLK signal to go high or low."""
    start_time = cocotb.utils.get_sim_time(units="ns")
    while True:
        await ClockCycles(dut.clk, 1)
        # Wait for half of the SCLK period (10 us)
        if (start_time + 100*100*0.5) < cocotb.utils.get_sim_time(units="ns"):
            break
    return

def ui_in_logicarray(ncs, bit, sclk):
    """Setup the ui_in value as a LogicArray."""
    return LogicArray(f"00000{ncs}{bit}{sclk}")

async def send_spi_transaction(dut, r_w, address, data):
    """
    Send an SPI transaction with format:
    - 1 bit for Read/Write
    - 7 bits for address
    - 8 bits for data
    
    Parameters:
    - r_w: boolean, True for write, False for read
    - address: int, 7-bit address (0-127)
    - data: LogicArray or int, 8-bit data
    """
    # Convert data to int if it's a LogicArray
    if isinstance(data, LogicArray):
        data_int = int(data)
    else:
        data_int = data
    # Validate inputs
    if address < 0 or address > 127:
        raise ValueError("Address must be 7-bit (0-127)")
    if data_int < 0 or data_int > 255:
        raise ValueError("Data must be 8-bit (0-255)")
    # Combine RW and address into first byte
    first_byte = (int(r_w) << 7) | address
    # Start transaction - pull CS low
    sclk = 0
    ncs = 0
    bit = 0
    # Set initial state with CS low
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    await ClockCycles(dut.clk, 1)
    # Send first byte (RW + Address)
    for i in range(8):
        bit = (first_byte >> (7-i)) & 0x1
        # SCLK low, set COPI
        sclk = 0
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
        # SCLK high, keep COPI
        sclk = 1
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
    # Send second byte (Data)
    for i in range(8):
        bit = (data_int >> (7-i)) & 0x1
        # SCLK low, set COPI
        sclk = 0
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
        # SCLK high, keep COPI
        sclk = 1
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
    # End transaction - return CS high
    sclk = 0
    ncs = 1
    bit = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    await ClockCycles(dut.clk, 600)
    return ui_in_logicarray(ncs, bit, sclk)

async def PWM_test(dut, signal, channel, num_cycles=3, timeout=5000000):
    """
    Sample and return freq and DC of PWM output
    """
    last_val = (int(signal.value) >> channel) & 1

    rising_edge = []
    time_high = []

    last_rise = None

    start_time = cocotb.utils.get_sim_time(units="ns")

    while len(rising_edge) - 1 < num_cycles:
        await ClockCycles(dut.clk, 1)
        now = cocotb.utils.get_sim_time(units="ns")

        curr_val = (int(signal.value) >> channel) & 1
        
        if now - start_time > timeout:
            return 1.0 if curr_val == 1 else 0.0, 0
        
        if curr_val == 1 and last_val == 0:
            #rising edge
            rising_edge.append(now)
            
            last_rise = now
        elif curr_val == 0 and last_val == 1:
            #falling edge
            if last_rise is not None:
                time_high.append(now - last_rise)
        
        last_val = curr_val

    periods = []
    for t1, t2 in zip(rising_edge, rising_edge[1:]):
        periods.append(t2-t1)

    avg_period = sum(periods)/len(periods)
    avg_tHigh = sum(time_high)/len(time_high)

    if avg_period > 0:
        duty = avg_tHigh/avg_period
        freq = (1E9)/avg_period
    else:
        duty = 0
        freq = 0
    
    return duty, freq

@cocotb.test()
async def test_spi(dut):
    dut._log.info("Start SPI test")

    # Set the clock period to 100 ns (10 MHz)
    clock = Clock(dut.clk, 100, units="ns")
    cocotb.start_soon(clock.start())

    # Reset
    dut._log.info("Reset")
    dut.ena.value = 1
    ncs = 1
    bit = 0
    sclk = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)

    dut._log.info("Test project behavior - SPI")
    dut._log.info("Write transaction, address 0x00, data 0xF0")
    ui_in_val = await send_spi_transaction(dut, 1, 0x00, 0xF0)  # Write transaction
    assert dut.uo_out.value == 0xF0, f"Expected 0xF0, got {dut.uo_out.value}"
    await ClockCycles(dut.clk, 1000) 

    dut._log.info("Write transaction, address 0x01, data 0xCC")
    ui_in_val = await send_spi_transaction(dut, 1, 0x01, 0xCC)  # Write transaction
    assert dut.uio_out.value == 0xCC, f"Expected 0xCC, got {dut.uio_out.value}"
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x30 (invalid), data 0xAA")
    ui_in_val = await send_spi_transaction(dut, 1, 0x30, 0xAA)
    await ClockCycles(dut.clk, 100)

    dut._log.info("Read transaction (invalid), address 0x00, data 0xBE")
    ui_in_val = await send_spi_transaction(dut, 0, 0x30, 0xBE)
    assert dut.uo_out.value == 0xF0, f"Expected 0xF0, got {dut.uo_out.value}"
    await ClockCycles(dut.clk, 100)
    
    dut._log.info("Read transaction (invalid), address 0x41 (invalid), data 0xEF")
    ui_in_val = await send_spi_transaction(dut, 0, 0x41, 0xEF)
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x02, data 0xFF")
    ui_in_val = await send_spi_transaction(dut, 1, 0x02, 0xFF)  # Write transaction
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x04, data 0xCF")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0xCF)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("Write transaction, address 0x04, data 0xFF")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0xFF)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("Write transaction, address 0x04, data 0x00")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0x00)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("Write transaction, address 0x04, data 0x01")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0x01)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("SPI test completed successfully")

@cocotb.test()
async def test_pwm_freq(dut):
    # Clock @ 10 MHz
    clock = Clock(dut.clk, 100, units="ns")
    cocotb.start_soon(clock.start())

    # Reset & basic IO setup
    dut._log.info("Reset")
    dut.ena.value = 1
    dut.ui_in.value = ui_in_logicarray(1, 0, 0)  # nCS=1, bit=0, sclk=0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)

    # Helper: wait for a bit level with timeout (returns time in ns)
    async def wait_for_level(bit_handle, level: int, max_cycles: int):
        for _ in range(max_cycles):
            await RisingEdge(dut.clk)
            if int(bit_handle.value) == level:
                return cocotb.utils.get_sim_time(units="ns")
        raise TestFailure(f"Timeout waiting for level {level}")

    # Helper: measure frequency of one bit by timing two rising edges
    async def measure_freq(bus_handle, bit_idx: int) -> float:
        sig = bus_handle[bit_idx]
        # Sync to LOW, then capture two consecutive rising edges
        await wait_for_level(sig, 0, 10000)
        t1 = await wait_for_level(sig, 1, 10000)
        await wait_for_level(sig, 0, 10000)
        t2 = await wait_for_level(sig, 1, 10000)
        period_ns = t2 - t1
        return 1e9 / period_ns  # Hz

    # Set 50% duty
    await send_spi_transaction(dut, 1, 0x04, 0x80)

    # Clear enables/modes
    for reg in (0x00, 0x01, 0x02, 0x03):
        await send_spi_transaction(dut, 1, reg, 0x00)

    # (en_reg, mode_reg, bus_handle, channel_base)
    banks = [
        (0x00, 0x02, dut.uo_out, 0),   # channels 0..7
        (0x01, 0x03, dut.uio_out, 8),  # channels 8..15
    ]

    dut._log.info("Testing PWM frequency on all channels")
    for en_reg, mode_reg, bus, base in banks:
        for i in range(8):
            ch = base + i
            # Enable channel and put it in PWM mode
            await send_spi_transaction(dut, 1, en_reg,  1 << i)
            await send_spi_transaction(dut, 1, mode_reg, 1 << i)

            # Allow generator to start toggling
            await ClockCycles(dut.clk, 2000)

            freq = await measure_freq(bus, i)
            assert 2970 <= freq <= 3030, (
                f"Channel {ch}: measured {freq:.1f} Hz; expected 3000 Hz ±1%"
            )

            # Disable this channel
            await send_spi_transaction(dut, 1, en_reg,  0x00)
            await send_spi_transaction(dut, 1, mode_reg, 0x00)

    # Reset duty to 0% at end
    await send_spi_transaction(dut, 1, 0x04, 0x00)
    dut._log.info("PWM frequency test completed successfully on all 16 channels")

@cocotb.test()
async def test_pwm_duty(dut):
    #Write your test here
    import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, ClockCycles
from cocotb.result import TestFailure

@cocotb.test()
async def test_pwm_duty_cycle_all_channels(dut):
    """Verify PWM duty = 0%, 50%, 100% on all 16 channels."""

    # --- Clock & reset ---
    clock = Clock(dut.clk, 100, units="ns")  # 10 MHz
    cocotb.start_soon(clock.start())

    dut.ena.value = 1
    dut.ui_in.value = ui_in_logicarray(1, 0, 0)  # nCS=1, bit=0, sclk=0

    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)

    # --- Helpers ---
    async def wait_for_level(sig, level: int, max_cycles: int) -> int:
        """Poll 'sig' on clk edges until it equals 'level'. Return sim time (ns)."""
        for _ in range(max_cycles):
            await RisingEdge(dut.clk)
            if int(sig.value) == level:
                return cocotb.utils.get_sim_time(units="ns")
        raise TestFailure(f"Timeout waiting for level {level}")

    async def measure_duty(sig, max_cycles: int = 20000) -> tuple[float, float]:
        """
        Measure duty cycle by timing high width and period:
          duty = high_ns / period_ns.
        Returns (duty_float_0_to_1, period_ns).
        """
        # sync to a LOW → RISE
        await wait_for_level(sig, 0, max_cycles)
        t1 = await wait_for_level(sig, 1, max_cycles)  # rising edge
        tf = await wait_for_level(sig, 0, max_cycles)  # falling edge
        t2 = await wait_for_level(sig, 1, max_cycles)  # next rising edge
        high_ns = tf - t1
        period_ns = t2 - t1
        if period_ns <= 0:
            raise TestFailure("Non-positive period measured")
        return (high_ns / period_ns, period_ns)

    async def is_constant(sig, target: int, sample_cycles: int = 7000) -> bool:
        """Check signal stays at 'target' for 'sample_cycles' clk edges."""
        for _ in range(sample_cycles):
            await RisingEdge(dut.clk)
            if int(sig.value) != target:
                return False
        return True

    # Clear enables/modes
    for reg in (0x00, 0x01, 0x02, 0x03):
        await send_spi_transaction(dut, 1, reg, 0x00)

    # Banks: (enable_reg, mode_reg, bus_handle, base_index)
    banks = [
        (0x00, 0x02, dut.uo_out, 0),   # channels 0..7
        (0x01, 0x03, dut.uio_out, 8),  # channels 8..15
    ]

    # --- Test all channels ---
    tol_pct = 1.0  # ±1% around 50%
    for en_reg, mode_reg, bus, base in banks:
        for i in range(8):
            ch = base + i

            # Enable this channel and set PWM mode
            await send_spi_transaction(dut, 1, en_reg,  1 << i)
            await send_spi_transaction(dut, 1, mode_reg, 1 << i)

            # 0% duty
            await send_spi_transaction(dut, 1, 0x04, 0x00)
            await ClockCycles(dut.clk, 7000)
            sig = bus[i]
            ok0 = await is_constant(sig, 0, sample_cycles=5000)
            assert ok0, f"Channel {ch}: expected 0% (always LOW), but it toggled"

            # 50% duty
            await send_spi_transaction(dut, 1, 0x04, 0x80)
            await ClockCycles(dut.clk, 7000)
            duty, period_ns = await measure_duty(sig)
            duty_pct = duty * 100.0
            assert (50 - tol_pct) <= duty_pct <= (50 + tol_pct), \
                (f"Channel {ch}: 50% test failed — measured {duty_pct:.2f}% "
                 f"(period {period_ns:.1f} ns), expected 50% ±{tol_pct}%")

            # 100% duty
            await send_spi_transaction(dut, 1, 0x04, 0xFF)
            await ClockCycles(dut.clk, 7000)
            ok1 = await is_constant(sig, 1, sample_cycles=5000)
            assert ok1, f"Channel {ch}: expected 100% (always HIGH), but it toggled"

            # Disable this channel
            await send_spi_transaction(dut, 1, en_reg,  0x00)
            await send_spi_transaction(dut, 1, mode_reg, 0x00)

    # Cleanup
    await send_spi_transaction(dut, 1, 0x04, 0x00)
    dut._log.info("PWM duty-cycle tests passed on all 16 channels")

