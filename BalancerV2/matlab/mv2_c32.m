function v = mv2_c32(b, o)
% MicroVib 32-bit number: [m0 m1 m2 exp], mant = m2 + m1/256 + m0/65536, value = mant * 2^(exp-72).
% Sign is bit 7 of the exponent byte (verified against MicroBase 2026-11-14).
e = double(b(o+3));
if e == 0, v = 0; return; end
v = (double(b(o+2)) + double(b(o+1))/256 + double(b(o))/65536) * 2^(bitand(e, 127) - 72);
if bitand(e, 128), v = -v; end
end
