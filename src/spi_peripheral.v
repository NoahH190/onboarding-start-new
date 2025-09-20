`default_nettype none
//testing for same
module spi_peripheral (
    input  wire COPI,
    input  wire nCS,
    input  wire SCLK,
    input  wire clk,
    input  wire rst_n,

    output wire [7:0] en_reg_out_7_0,
    output wire [7:0] en_reg_out_15_8,
    output wire [7:0] en_reg_pwm_7_0,
    output wire [7:0] en_reg_pwm_15_8,
    output reg  [7:0] pwm_duty_cycle
);

  // 2-FF synchronizers
  reg sclk_s1, sclk_s2, copi_s1, copi_s2, ncs_s1, ncs_s2;
  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      sclk_s1 <= 1'b0; sclk_s2 <= 1'b0;
      copi_s1 <= 1'b0; copi_s2 <= 1'b0;
      ncs_s1  <= 1'b1; ncs_s2  <= 1'b1;
    end else begin
      sclk_s1 <= SCLK;  sclk_s2 <= sclk_s1;
      copi_s1 <= COPI;  copi_s2 <= copi_s1;
      ncs_s1  <= nCS;   ncs_s2  <= ncs_s1;
    end
  end

  wire sclk_sync = sclk_s2;
  wire copi_sync = copi_s2;
  wire ncs_sync  = ncs_s2;

  // Edge detect
  reg sclk_q, ncs_q;
  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      sclk_q <= 1'b0;
      ncs_q  <= 1'b1;
    end else begin
      sclk_q <= sclk_sync;
      ncs_q  <= ncs_sync;
    end
  end

  wire sclk_rise =  sclk_sync & ~sclk_q;
  wire ncs_fall  = ~ncs_sync  &  ncs_q;

  // SPI shift & decode
  reg [15:0] shift_reg;
  reg [4:0]  bit_cnt;
  reg        in_frame;

  // Internal wide regs mapped to split outputs
  reg [15:0] en_out;
  reg [15:0] en_pwm_mode;

  assign en_reg_out_7_0   = en_out[7:0];
  assign en_reg_out_15_8  = en_out[15:8];
  assign en_reg_pwm_7_0   = en_pwm_mode[7:0];
  assign en_reg_pwm_15_8  = en_pwm_mode[15:8];

  // Precompute the shifted value that includes the new bit
  wire [15:0] next_shift = {shift_reg[14:0], copi_sync};

  // SINGLE writer for en_out, en_pwm_mode, pwm_duty_cycle, shift_reg, bit_cnt, in_frame
  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      en_out         <= 16'h0000;
      en_pwm_mode    <= 16'h0000;
      pwm_duty_cycle <= 8'h00;
      shift_reg      <= 16'd0;
      bit_cnt        <= 5'd0;
      in_frame       <= 1'b0;
    end else begin
      // Start frame on nCS falling edge
      if (ncs_fall) begin
        in_frame <= 1'b1;
        bit_cnt  <= 5'd0;
      end

      // Shift on SCLK rising while CS is low
      if (in_frame && !ncs_sync && sclk_rise) begin
        shift_reg <= next_shift;
        bit_cnt   <= bit_cnt + 5'd1;

        // 16th bit just arrived (old bit_cnt == 15)
        if (bit_cnt == 5'd15) begin
          in_frame <= 1'b0;

          if (next_shift[15]) begin
            case (next_shift[14:8])
              7'h00: en_out[7:0]        <= next_shift[7:0];
              7'h01: en_out[15:8]       <= next_shift[7:0];
              7'h02: en_pwm_mode[7:0]   <= next_shift[7:0];
              7'h03: en_pwm_mode[15:8]  <= next_shift[7:0];
              7'h04: pwm_duty_cycle     <= next_shift[7:0];
              default: /* no write */;
            endcase
          end
        end
      end

      // Abort frame if CS deasserts
      if (ncs_sync) begin
        in_frame <= 1'b0;
      end
    end
  end
endmodule

