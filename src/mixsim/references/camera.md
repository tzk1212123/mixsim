# Virtual camera operating reference

Read rgb for a fresh synthetic ROI measurement: a mean of 5 independent RGB frames by default, with 0.6 digital-number Gaussian noise per channel per frame and clipping to 0..255. Repeated reads draw fresh camera noise but do not advance flow or time. This is not an OpenCV capture or real USB camera driver.

The target is a nominal mixture of synthetic amber/blue optical-density vectors. Beer–Lambert absorption provides a nonlinear, configurable RGB response. Stock spectra, lighting and path length have not been calibrated. RGB values use a simplified linear camera-channel response, not a measured sRGB color space.

The objective is RGB root-mean-square error in digital numbers, not chemical yield and not perceptual Delta E. Target RGB and the success tolerance (3 RGB DN) are returned by list_devices. RGB after a flow change can retain old liquid: the model has plug-flow transport plus a well-mixed chamber. Settle before measuring; 60 s is appropriate at the default 400 uL/min total. Pump bias means the nominal target recipe may not be the best command ratio.

A trial's best noisy observation is not delivered performance. Recommend a successful trial, then finalize to rerun the same setting with fresh measurements. Report the final replicate separately even when its error is worse. An aborted replicate cannot complete a campaign. The dashboard's noise-free color and actual flow are display-only diagnostics, never agent measurements.
