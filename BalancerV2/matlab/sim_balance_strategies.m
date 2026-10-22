% sim_balance_strategies.m
% Monte Carlo of correction strategies on a synthetic rotor whose true influence
% coefficient differs from the seed, with measurement noise and 1 g rounding.
% Strategies: MicroVib snapshot (replace coefficient after each move above the learn
% limit), blended learning (trust 0.5), and seed only (never learn). Also compares a
% single-regime move against a two-regime least-squares move when ground and hover
% respond differently. Run from this folder: sim_balance_strategies
clear; clc;
addpath(fileparts(mfilename('fullpath')));   % so the mv2_* functions resolve from any folder rng(2);

trials   = 300;
maxFlights = 8;
target   = 0.20;           % IPS acceptance
noise    = 0.02;           % IPS measurement noise, 1 sigma, each axis
seedSens = 320; seedTach = 340;
learnLimit = 0.10;
positions = [0 90 180 270]; maxPerBolt = 400;

strategies = {'MicroVib snapshot', 'blended trust 0.5', 'seed only'};
trust = [1.0, 0.5, 0];
flightsNeeded = nan(trials, numel(strategies));
finalLevel = nan(trials, numel(strategies));

for tr = 1:trials
    % true rotor: coefficient within +/-40% of seed in sensitivity, +/-30 deg in angle,
    % initial imbalance 0.3 to 1.2 IPS at a random phase
    trueSens = seedSens*(1 + 0.4*(2*rand-1)); trueTach = seedTach + 30*(2*rand-1);
    v0 = (0.3 + 0.9*rand)*exp(1i*deg2rad(360*rand));
    for sIdx = 1:numel(strategies)
        v = v0; sens = seedSens; tach = seedTach;
        prev = []; n = NaN;
        for fl = 1:maxFlights
            m = v + noise*(randn + 1i*randn);                      % measured vector
            level = abs(m); phase = mod(rad2deg(angle(m)), 360);
            if level <= target, n = fl - 1; break; end
            % learn from the previous move
            if ~isempty(prev) && trust(sIdx) > 0
                [ls, lt, dl] = mv2_learn(prev.level, prev.phase, level, phase, prev.chg(1), prev.chg(2));
                if dl >= learnLimit, [sens, tach] = mv2_blend(sens, tach, ls, lt, trust(sIdx)); end
            end
            [mag, ang] = mv2_solve(level, phase, sens, tach);
            sp = mv2_split(mag, ang, positions);
            sp(:,2) = min(round(sp(:,2)), maxPerBolt);              % whole grams, bolt limit
            % apply on the true rotor: each weight w at angle a adds (w/trueSens) e^{i(-a-trueTach)}
            applied = 0;
            for i = 1:size(sp,1)
                v = v + (sp(i,2)/trueSens)*exp(1i*deg2rad(-sp(i,1) - trueTach));
                applied = applied + sp(i,2)*exp(1i*deg2rad(sp(i,1)));
            end
            prev.level = level; prev.phase = phase;
            prev.chg = [abs(applied), mod(rad2deg(angle(applied)), 360)];
        end
        if isnan(n), n = maxFlights; end
        flightsNeeded(tr, sIdx) = n; finalLevel(tr, sIdx) = abs(v);
    end
end
fprintf('single regime, %d rotors, noise %.2f IPS, coefficient error up to 40%% / 30 deg\n', trials, noise);
fprintf('%-20s %10s %10s %12s\n', 'strategy', 'mean runs', 'p90 runs', 'not done');
for sIdx = 1:numel(strategies)
    fn = flightsNeeded(:, sIdx);
    fprintf('%-20s %10.2f %10.0f %11.0f%%\n', strategies{sIdx}, mean(fn), prctile_(fn, 90), 100*mean(finalLevel(:,sIdx) > target));
end

% ---- two regimes, one adjustment ----
% ground and hover respond with different coefficients; a move that zeroes one leaves the
% other. Compare "solve on the worst regime" against weighted least squares over both.
fprintf('\ntwo regimes sharing hub weights: worst-regime move vs least squares\n');
res = zeros(trials, 2);
for tr = 1:trials
    sG = 320*(1 + 0.2*(2*rand-1)); tG = 340 + 15*(2*rand-1);
    sH = 320*(1 + 0.2*(2*rand-1)); tH = 340 + 40*(2*rand-1);      % hover differs more
    vG = (0.2 + 0.6*rand)*exp(1i*deg2rad(360*rand));
    vH = vG*(0.8 + 0.4*rand)*exp(1i*deg2rad(30*(2*rand-1)));      % related but not identical
    lv = [abs(vG) abs(vH)]; ph = mod(rad2deg(angle([vG vH])), 360);
    % assume the coefficients are known (what learning converges to)
    [m1, a1] = mv2_solve(lv(lv == max(lv)), ph(lv == max(lv)), 320, 340);     % worst regime, seed coefficient
    [m2, a2] = mv2_solve(lv, ph, [sG sH], [tG tH], [1 1]);                      % LS with learned coefficients
    after = @(mag, ang) max(abs(vG + (mag/sG)*exp(1i*deg2rad(-ang - tG))), abs(vH + (mag/sH)*exp(1i*deg2rad(-ang - tH))));
    res(tr, :) = [after(m1, a1), after(m2, a2)];
end
fprintf('%-28s %12s %12s\n', 'method', 'mean worst', 'p90 worst');
fprintf('%-28s %12.3f %12.3f\n', 'worst regime, seed coef', mean(res(:,1)), prctile_(res(:,1), 90));
fprintf('%-28s %12.3f %12.3f\n', 'LS both, learned coef', mean(res(:,2)), prctile_(res(:,2), 90));
fprintf('(remaining IPS on the worse of the two regimes after one move)\n');
