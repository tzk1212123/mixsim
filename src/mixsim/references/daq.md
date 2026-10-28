# Virtual DAQ operating reference

The NI USB-6003 measures voltage, not pressure or temperature directly. The virtual input quantizer uses a 16-bit +-10 V range, based on its specification. This model samples at the integration rate (10 Hz by default), not the hardware maximum 100 kS/s aggregate.

ASSUMED external pressure transducer: 0..100 kPa maps to 0..5 V. Assumed pressure noise standard deviation is 0.08 kPa before quantization. Neither a real sensor model nor its calibration was provided. Pressure is derived from a reduced-order circular-tube hydraulic resistance and lag, not measured bench data.

Read channels pressure_kpa, pressure_voltage_v and temperature_c. Temperature is a noisy read-only ambient value, 25 C by default. There is no heater or thermal-control experiment. Writes to heater, pressure or temperature are rejected identically from Python, CLI and MCP.

The interlock is sampled inside the virtual device integration loop and independent of any planner. The latest sample is cached: repeatedly reading the DAQ or polling the dashboard does not advance time or draw new noise. Query list_devices for current trip/reset thresholds. The thresholds are assumed project limits, not certified hardware ratings.
