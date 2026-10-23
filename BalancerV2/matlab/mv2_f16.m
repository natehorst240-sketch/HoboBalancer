function v = mv2_f16(b, o)
% MicroVib 16-bit number: [mant u8][exp u8], value = mant * 2^(exp-72). o is 1-based.
m = double(b(o)); e = double(b(o+1));
if e == 0 && m == 0, v = 0; else, v = m * 2^(e - 72); end
end
