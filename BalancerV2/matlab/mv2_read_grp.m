function g = mv2_read_grp(path)
% Read a MicroVib II group file (.grp) or the group section of a history file (.HST).
% Returns g.name and g.tasks(k) with name, enabled, sens, tach, flags, positions (deg), unit, labels.
fid = fopen(path, 'rb');
if fid < 0, error('mv2_read_grp:open', 'cannot open %s', path); end
b = fread(fid, [1 inf], 'uint8=>uint8'); fclose(fid);
g.name = strtrim(char(b(1:8)));
g.tasks = struct('name', {}, 'enabled', {}, 'sens', {}, 'tach', {}, 'flags', {}, 'positions', {}, 'unit', {}, 'labels', {});
for i = 0:9
    o = 16 + i*180 + 1;                       % 1-based start of record
    t.name = strtrim(cstr(b(o:o+7)));
    t.enabled = b(o+8) ~= 0;
    t.sens = mv2_f16(b, o+11); t.tach = mv2_f16(b, o+15);
    t.flags = double(b(o+17)) + 256*double(b(o+18));
    n = min(double(b(o+19)), 8);
    t.positions = zeros(1, n); t.labels = cell(1, n); t.unit = '';
    for k = 0:n-1
        e = o + 20 + 20*k;
        t.unit = strtrim(cstr(b(e:e+7)));
        t.positions(k+1) = mv2_f16(b, e+8);
        t.labels{k+1} = strtrim(cstr(b(e+10:e+17)));
    end
    g.tasks(end+1) = t;
end
end
function s = cstr(bytes)
z = find(bytes == 0, 1); if isempty(z), s = char(bytes); else, s = char(bytes(1:z-1)); end
end
