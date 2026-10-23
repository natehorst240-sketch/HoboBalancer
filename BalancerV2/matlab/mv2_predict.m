function [level, phase] = mv2_predict(level0, phase0, sens, tach, mag, ang)
% Predicted vibration after applying a correction (mag at ang) with coefficient sens/tach.
v = level0*exp(1i*deg2rad(phase0)) + (mag/sens)*exp(1i*deg2rad(-ang - tach));
level = abs(v); phase = mod(rad2deg(angle(v)), 360);
end
