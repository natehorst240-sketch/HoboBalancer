function v = mv2_c32(b, o)
% MicroVib 32-bit number: [m0 m1 m2 exp], mant = m2 + m1/256 + m0/65536, value = mant * 2^(exp-72).
e = double(b(o+3));
if e == 0, v = 0; else, v = (double(b(o+2)) + double(b(o+1))/256 + double(b(o))/65536) * 2^(e - 72); end
end
