function [sens, tach] = mv2_blend(oldSens, oldTach, newSens, newTach, trust)
% Blend an old coefficient with a measured one; trust = 1 reproduces the MicroVib.
sens = exp((1-trust)*log(oldSens) + trust*log(newSens));
tach = mod(rad2deg(angle((1-trust)*exp(1i*deg2rad(oldTach)) + trust*exp(1i*deg2rad(newTach)))), 360);
end
