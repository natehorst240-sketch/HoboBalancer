% test_solver_history.m
% Regression test of the balance math against MicroVib II records.
% 1. A1090731.HST: every run's solution must match the MicroVib's own split.
% 2. A1090021.HST runs 2 -> 3: the learned coefficient must match SENS 1206 / TACH 97.
% Run from this folder: test_solver_history
clear; clc;
addpath(fileparts(mfilename('fullpath')));   % so the mv2_* functions resolve from any folder
% MicroVib files ship in ./data next to this script; fall back to ../profiles in the repo
here = fileparts(mfilename('fullpath')); if isempty(here), here = pwd; end
prof = fullfile(here, 'data');
if ~exist(fullfile(prof, 'A1090731.HST'), 'file'), prof = fullfile(here, '..', 'profiles'); end
if ~exist(fullfile(prof, 'A1090731.HST'), 'file'), prof = mv2_sample_data(); end   % embedded copies
[runs, g] = mv2_read_hst(fullfile(prof, 'A1090731.HST'));
fprintf('%-9s %-17s %6s %7s %7s  %-24s  %-24s\n', 'task', 'when', 'rpm', 'level', 'phase', 'ours', 'MicroVib');
worst = 0;
for k = 1:numel(runs)
    r = runs(k);
    t = g.tasks(strcmp({g.tasks.name}, r.task));
    [mag, ang] = mv2_solve(r.level, r.phase, r.sens, r.tach);
    sp = mv2_split(mag, ang, t.positions);
    ours = sprintf('%.2f@%g ', [sp(:,2) sp(:,1)]'); theirs = sprintf('%.2f@%g ', r.adj');
    fprintf('%-9s %-17s %6.1f %7.3f %7.1f  %-24s  %-24s\n', r.task, datestr(r.when, 'yyyy-mm-dd HH:MM'), r.rpm, r.level, r.phase, ours, theirs);
    % compare amounts at matching angles
    for i = 1:size(r.adj, 1)
        m = sp(sp(:,1) == r.adj(i,2), 2); if isempty(m), m = 0; end
        worst = max(worst, abs(m - r.adj(i,1)));
    end
end
assert(worst < 0.02, 'solution mismatch %.3f', worst);
fprintf('all %d solutions reproduce the MicroVib within %.3f units\n\n', numel(runs), worst);

runs2 = mv2_read_hst(fullfile(prof, 'A1090021.HST'));
r3 = runs2(3);   % its solution fields are garbled in this file; levels come from the MicroVib screen
[s, t, dl] = mv2_learn(0.789, 24.8, 0.933, 36.9, r3.change(1), r3.change(2));
fprintf('learned from %.1f g at %g: SENS %.1f TACH %.1f (file says %.1f / %.1f), change %.3f IPS\n', r3.change(1), r3.change(2), s, t, r3.sens, r3.tach, dl);
assert(abs(s - r3.sens) < 2 && abs(t - r3.tach) < 0.5, 'learning mismatch');
% blended alternative and a two-regime least-squares check
[bs, bt] = mv2_blend(320, 340, s, t, 0.5);
fprintf('blended at trust 0.5: SENS %.1f TACH %.1f\n', bs, bt);
lt = runs(ismember({runs.task}, {'GND LT', 'HOV LT'}));
[mag, ang] = mv2_solve([lt.level], [lt.phase], [lt.sens], [lt.tach], [1 1]);
fprintf('one weight move for GND LT and HOV LT together: %.2f g at %.1f deg\n', mag, ang);
for k = 1:numel(lt)
    [lv, ~] = mv2_predict(lt(k).level, lt(k).phase, lt(k).sens, lt(k).tach, mag, ang);
    fprintf('  %-7s %.3f -> %.3f IPS\n', lt(k).task, lt(k).level, lv);
end
disp('PASS');
