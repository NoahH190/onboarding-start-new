<!---

This file is used to generate your project datasheet. Please fill in the information below and delete any unused
sections.

You can also include images in this folder and reference them in the markdown. Each image must be less than
512 kb in size, and the combined size of all images must be less than 1 MB.
-->

## How it works

Your project implements briefly describe the core function—e.g., “an SPI-controlled peripheral that allows external devices to configure enable registers, PWM modes, and duty cycles via serial input

## How to test

Use a Verilog testbench with a clock generator and reset logic.
Drive COPI, SCLK, and nCS with known patterns (representing SPI transfers). Check that the output registers update correctly Optionally, dump a waveform (.vcd file) and verify timing in GTKWave.

## External hardware

None are being used
