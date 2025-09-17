`default_nettype none


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
    output wire [7:0] pwm_duty_cycle
);

reg sclk_s1, sclk_s2, copi_s1, copi_s2, ncs_s1, ncs_s2; // implementtion of 2 ff synchronizer for each input

always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        sclk_s1 <= 1'b0; 
        sclk_s2 <= 1'b0; // reset 
        copi_s1 <= 1'b0; 
        copi_s2 <= 1'b0;
        ncs_s1  <= 1'b1; 
        ncs_s2  <= 1'b1; 
    end else begin
        sclk_s1 <= SCLK;  // synchronizes clocks and such
        sclk_s2 <= sclk_s1;
        copi_s1 <= COPI;  
        copi_s2 <= copi_s1;
        ncs_s1  <= nCS;   
        ncs_s2  <= ncs_s1;
    end
end

wire sclk_sync = sclk_s2; //Renaming syncronized signals for clarity
wire copi_sync = copi_s2;
wire ncs_sync  = ncs_s2;

reg sclk_q, ncs_q; // delayed versions of SCLK and nCS for edge detection

always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        sclk_q <= 1'b0;
        ncs_q  <= 1'b1; 
    end else begin
        sclk_q <= sclk_sync;  // remember previous value of SCLK
        ncs_q  <= ncs_sync;   // remember previous value of nCS
    end
end

wire sclk_rise =  sclk_sync & ~sclk_q; // detect rising edge of SCLK
wire ncs_fall  = ~ncs_sync  &  ncs_q;

reg [15:0] shift_reg;
reg [4:0]  bit_cnt;
reg        in_frame;


reg [15:0] en_out;
reg [15:0] en_pwm_mode;
reg [7:0]  pwm_duty_cycle;

// Map internal regs to the split 8-bit outputs expected by top
assign en_reg_out_7_0   = en_out[7:0];
assign en_reg_out_15_8  = en_out[15:8];
assign en_reg_pwm_7_0   = en_pwm_mode[7:0];
assign en_reg_pwm_15_8  = en_pwm_mode[15:8];
assign pwm_duty_cycle   = pwm_duty_cycle_r;

wire [15:0] next_shift = {shift_reg[14:0], copi_sync};

always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        en_out         <= 16'h0000;
        en_pwm_mode    <= 16'h0000;
        pwm_duty_cycle <= 8'h00;
        shift_reg      <= 16'd0;
        bit_cnt        <= 5'd0;
        in_frame       <= 1'b0;
    end 
    else begin
        if (ncs_fall) begin
            in_frame <= 1'b1;
            bit_cnt  <= 5'd0;
        end
    end

    if (in_frame && !ncs_sync && sclk_rise) begin
            shift_reg <= {shift_reg[14:0], copi_sync};
            bit_cnt   <= bit_cnt + 5'd1;

            if (bit_cnt == 5'd15) begin
                in_frame <= 1'b0;
                
                if (shift_reg[15]) begin
                     case (shift_reg[14:8])
                        7'h00: en_out[7:0]        <= shift_reg[7:0];
                        7'h01: en_out[15:8]       <= shift_reg[7:0];
                        7'h02: en_pwm_mode[7:0]   <= shift_reg[7:0];
                        7'h03: en_pwm_mode[15:8]  <= shift_reg[7:0];
                        7'h04: pwm_duty_cycle     <= shift_reg[7:0];
                        default: ;
                    endcase
                end
            end           
        end
        if (ncs_sync) begin
            in_frame <= 1'b0;
       end
    end
endmodule