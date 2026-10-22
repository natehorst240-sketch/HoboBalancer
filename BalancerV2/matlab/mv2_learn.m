function [sens, tach, dlevel] = mv2_learn(prevLevel, prevPhase, newLevel, newPhase, chgMag, chgLoc)
% MicroVib single-step coefficient from a move: change (chgMag at chgLoc deg) took the
% vector from prev to new. Returns the measured sens, tach and the size of the change.
d = newLevel*exp(1i*deg2rad(newPhase)) - prevLevel*exp(1i*deg2rad(prevPhase));
dlevel = abs(d);
sens = chgMag / dlevel;
tach = mod(-rad2deg(angle(d)) - chgLoc, 360);
end
