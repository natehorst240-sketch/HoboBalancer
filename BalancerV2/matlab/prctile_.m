function p = prctile_(x, q)
% Percentile without the Statistics Toolbox.
x = sort(x(:)); n = numel(x);
k = max(1, min(n, round(q/100*(n-1) + 1)));
p = x(k);
end
