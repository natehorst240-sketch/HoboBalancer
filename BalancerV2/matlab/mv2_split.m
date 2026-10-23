function out = mv2_split(mag, ang, positions)
% Split a correction (mag at ang) onto the two adjacent positions that bracket it.
% out is [angle amount; angle amount].
p = sort(positions(:))';
i = find(p > ang, 1); if isempty(i), i = 1; end
j = i - 1; if j < 1, j = numel(p); end
a1 = p(j); a2 = p(i);
A = [cosd(a1) cosd(a2); sind(a1) sind(a2)];
w = A \ [mag*cosd(ang); mag*sind(ang)];
out = [a1 w(1); a2 w(2)];
out = out(abs(out(:,2)) > 1e-9, :);
end
