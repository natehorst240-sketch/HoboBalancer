function [b, a] = lp_biquad(fc, fs)
% 2nd-order Butterworth low-pass biquad by bilinear transform.
K = tan(pi*fc/fs); q = 1/sqrt(2);
n = 1/(1 + K/q + K*K);
b = [K*K*n, 2*K*K*n, K*K*n];
a = [1, 2*(K*K - 1)*n, (1 - K/q + K*K)*n];
end
