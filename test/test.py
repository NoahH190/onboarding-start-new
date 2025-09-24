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

    dut._log.info("Test project behavior")
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
    # Write your test here
    #####


    # Start the clock (100 MHz)
    clock = Clock(dut.clk, 10, units="ns")
    cocotb.start_soon(clock.start())
    
    # Enable the design
    dut.ena.value = 1
    
    # Reset the system
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value = 1
    
    # Enable PWM output and set to 50% duty cycle for reliable measurement
    await send_spi_transaction(dut, 1, 0x00, 0x01)  # Enable output for channel 0
    await send_spi_transaction(dut, 1, 0x02, 0x01)  # Enable PWM mode
    await send_spi_transaction(dut, 1, 0x04, 0x80)  # Set 50% duty cycle
    
    for _ in range(1000):
        await RisingEdge(dut.clk)
        if not int(dut.uo_out.value) in (0, 1):
            continue
        break

    await RisingEdge(dut.uo_out[0])
    t1 = int(cocotb.utils.get_sim_time(units="ns"))
    await RisingEdge(dut.uo_out[0])
    t2 = int(cocotb.utils.get_sim_time(units="ns"))

    period_ns = t2 - t1
    assert period_ns > 0, "Measured non-positive period"

    frequency = 1e9 / period_ns  # Hz

    assert 2970 <= frequency <= 3030, \
        f"PWM frequency {frequency:.1f} Hz outside 3000 Hz ±1%"
    dut._log.info(f"Measured PWM frequency: {frequency:.2f} Hz")


@cocotb.test()
async def test_pwm_duty(dut):
    #####
    # Write your test here



# Start the clock (100 MHz)
    clock = Clock(dut.clk, 10, units="ns")
    cocotb.start_soon(clock.start())
    
    # Enable the design
    dut.ena.value = 1
    
    # Reset the system
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value = 1
    
    # Test cases: 0%, 50%, and 100% duty cycles
    test_cases = [
        (0x00, 0),    # 0%
        (0x80, 50),   # 50%
        (0xFF, 100)   # 100%
    ]
    
    for duty_reg, expected_duty in test_cases:
        # Configure PWM for ch0
        await send_spi_transaction(dut, 1, 0x00, 0x01)  # enable output
        await send_spi_transaction(dut, 1, 0x02, 0x01)  # PWM mode
        await send_spi_transaction(dut, 1, 0x04, duty_reg)

        # Handle edge cases early
        if expected_duty == 0:
            # Give it a little time to settle
            await ClockCycles(dut.clk, 1000)
            assert (int(dut.uo_out.value) & 1) == 0, "Should be low at 0% duty"
            continue
        if expected_duty == 100:
            await ClockCycles(dut.clk, 1000)
            assert (int(dut.uo_out.value) & 1) == 1, "Should be high at 100% duty"
            continue

        # Measure within one period: rise -> fall -> next rise
        await RisingEdge(dut.uo_out[0])
        t_rise1 = int(cocotb.utils.get_sim_time(units="ns"))

        await FallingEdge(dut.uo_out[0])
        t_fall = int(cocotb.utils.get_sim_time(units="ns"))

        await RisingEdge(dut.uo_out[0])
        t_rise2 = int(cocotb.utils.get_sim_time(units="ns"))

        period = t_rise2 - t_rise1
        high_time = t_fall - t_rise1
        assert period > 0 and 0 <= high_time <= period, "Bad timing window"

        measured_duty = 100.0 * high_time / period

        assert abs(measured_duty - expected_duty) <= 1.0, \
            f"Duty {measured_duty:.1f}% != expected {expected_duty}% ±1%"
        dut._log.info(f"Duty OK: {measured_duty:.2f}% (expected {expected_duty}%)")

    dut._log.info("PWM Duty Cycle test completed successfully")
