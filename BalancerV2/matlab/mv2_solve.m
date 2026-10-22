function [mag, ang] = mv2_solve(level, phase, sens, tach, weight)
% Weighted least-squares correction for one adjustment shared by several regimes.
% Vectors level, phase (deg), sens (units per IPS), tach (deg), weight. Returns the
% correction magnitude (adjustment units) and its angle on the rotor (deg).
% Single regime reduces to the MicroVib rule: mag = sens*level, ang = -(phase+tach+180).
if nargin < 5, weight = ones(size(level)); end
k = exp(-1i*deg2rad(tach(:))) ./ sens(:);            % per-regime influence, per unit of conj(z)
v = level(:) .* exp(1i*deg2rad(phase(:)));
w = weight(:);
u = -sum(w .* conj(k) .* v) / sum(w .* abs(k).^2);   % u = conj(z)
z = conj(u);
mag = abs(z); ang = mod(rad2deg(angle(z)), 360);
end
