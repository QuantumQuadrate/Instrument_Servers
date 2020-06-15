"""
Timed loop with Python built-in module 'time'
"""

from time import perf_counter_ns, perf_counter
from numpy import empty, std, mean

runs = 1000 # iterations
freq = 1000 # [Hz]
tau = 1000/(freq) # [ms]

# 1kHz loop

dtimes = empty(runs, int)

t0 = perf_counter_ns()
# t0 = perf_counter()

scl = 1e-6 # to convert ns to ms
# scl = 1e3 # to convert second to ms

# t_init = perf_counter_ns()
t_init = perf_counter()

for i in range(runs):

    # do some stuff which takes dt < 1/freq
    
    # using perf_counter_ns:
    while True:
        dtimes[i] = perf_counter_ns() - t0
        if dtimes[i]*scl > tau: # compare time in ms
            #print('t_iter:',dtimes[i])
            t0 = perf_counter_ns()
            break
            
    # using perf_counter: result is fractional seconds
    # while True:
            # dtimes[i] = perf_counter() - t0 # units in ms
            # if dtimes[i]*scl > tau: # compare time in ms
                # print('t_iter:',dtimes[i])
                # t0 = perf_counter()
                # break

# t_elapsed = (perf_counter_ns() - t_init)*scl # [ms]
t_elapsed = (perf_counter() - t_init)*scl

dt_avg = mean(dtimes)
dt_std = std(dtimes)

print(f'runs={runs} \n'+ # loop iterations
        f'f={freq/1000}kHz \n'+ # loop frequency
        f'dt_avg={dt_avg*scl}[ms] \n'+ # measured loop period std
        f'dt_std={dt_std*scl}[ms] \n'+ # measured loop period std
        f'loop duration={t_elapsed}[ms] \n'+ # actual time elapsed, by measuring loop duration directly
        f'sum(dt) = {sum(dtimes)*scl}[ms] \n'+ # total time elapsed, according to counted time
        f'ghost time = {t_elapsed-sum(dtimes)*scl}[ms]') # time unaccounted for in loop timing
    
