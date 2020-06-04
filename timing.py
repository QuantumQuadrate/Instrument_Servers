"""
Timed loop with Python built-in module 'time'
"""

from time import perf_counter_ns
from numpy import empty, std, mean

runs = 1000 # run for 1000/1 kHz = 1 s
freq = 1000 # [Hz]
tau = 1000/(freq) # [ms]

# 1kHz loop

dtimes = empty(runs, int)

t0 = perf_counter_ns()

t_init = perf_counter_ns()
for i in range(runs):

    # do some stuff which takes dt < 1/freq
    
    while True:
        dtimes[i] = perf_counter_ns() - t0
        if dtimes[i]/1e6 > tau: # compare time in ms
            # print('t_iter:',dtimes[i])
            t0 = perf_counter_ns()
            break

t_elapsed = (perf_counter_ns() - t_init)/1e6 # [ms]

dt_avg = mean(dtimes)
dt_std = std(dtimes)

print(f'runs={runs} \n'+ # loop iterations
        f'f={freq/1000}kHz \n'+ # loop frequency
        f'dt_avg={dt_avg/1e6}[ms] \n'+ # measured loop period std
        f'dt_std={dt_std/1e6}[ms] \n'+ # measured loop period std
        f'loop duration={t_elapsed}[ms] \n'+ # actual time elapsed, by measuring loop duration directly
        f'sum(dt) = {sum(dtimes)/1e6}[ms] \n'+ # total time elapsed, according to counted time
        f'ghost time = {t_elapsed-sum(dtimes)/1e6}[ms]') # time unaccounted for in loop timing
    
