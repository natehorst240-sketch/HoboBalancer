function [runs, g] = mv2_read_hst(path)
% Read a MicroVib II history file. runs(k): task, when (datenum), avgs, rpm, level, phase,
% sens, tach, adj (2x2: amount, angle), change (mag, loc), prevLevel, prevPhase.
% Record layout per BalancerV2/profiles/decode_grp.py.
g = mv2_read_grp(path);
fid = fopen(path, 'rb'); b = fread(fid, [1 inf], 'uint8=>uint8'); fclose(fid);
runs = struct('task', {}, 'when', {}, 'avgs', {}, 'rpm', {}, 'level', {}, 'phase', {}, 'sens', {}, 'tach', {}, 'adj', {}, 'change', {}, 'prevLevel', {}, 'prevPhase', {});
o = 1817;
while o + 85 <= numel(b)
    if ~(b(o+6) == 3 && b(o+7) == 195 && b(o+8) == 27), o = o + 1; continue; end
    ti = double(b(o)) + 1;
    day = double(b(o+2)) + 256*double(b(o+3)); tm = double(b(o+4)) + 256*double(b(o+5));
    r.task = g.tasks(ti).name;
    r.when = datenum(1980, 1, 1) + day + tm*2/86400;
    r.avgs = double(b(o+21));
    r.rpm = le_f32(b, o+24) * 60/64;
    r.phase = mv2_c32(b, o+32);
    r.prevLevel = mv2_c32(b, o+36); r.prevPhase = mv2_c32(b, o+40);
    r.change = [mv2_c32(b, o+44), mv2_c32(b, o+48)];
    r.sens = mv2_c32(b, o+52); r.tach = mv2_c32(b, o+56);
    r.adj = [mv2_c32(b, o+60), mv2_c32(b, o+64); mv2_c32(b, o+72), mv2_c32(b, o+76)];
    d = mod(abs(r.adj(1,2) - r.adj(2,2)), 360);
    if d == 90 || d == 270, mag = hypot(r.adj(1,1), r.adj(2,1));
    elseif d == 180, mag = abs(r.adj(1,1) - r.adj(2,1));
    else, mag = r.adj(1,1) + r.adj(2,1); end
    if r.sens > 0, r.level = mag / r.sens; else, r.level = le_f32(b, o+28); end
    runs(end+1) = r;
    o = o + 86;
end
end
function v = le_f32(b, o)
v = double(typecast(uint8(b(o:o+3)), 'single'));
end
