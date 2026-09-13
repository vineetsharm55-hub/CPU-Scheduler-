# scheduler.py
# Contains all CPU scheduling algorithms.
# Adapted from the original terminal-based code to return structured data
# instead of printing — so Flask can send results as JSON to the frontend.

from copy import deepcopy

# ─── EMA / ML settings ────────────────────────────────────────────────────────
ALPHA = 0.65          # smoothing factor for Exponential Moving Average
ema_table = {}        # stores EMA values per PID across calls

# ─── ML helper functions ───────────────────────────────────────────────────────

def ml_predict(pid, default):
    """Return the EMA-predicted burst for a PID, or 'default' if unseen."""
    return round(ema_table.get(pid, default), 2)

def ml_update(pid, actual):
    """Update (or initialise) the EMA for a PID after observing 'actual' burst."""
    if pid in ema_table:
        ema_table[pid] = ALPHA * actual + (1 - ALPHA) * ema_table[pid]
    else:
        ema_table[pid] = float(actual)

def ml_accuracy(procs):
    """Return prediction accuracy (%) averaged over all processes."""
    errors = [
        abs(p['predicted'] - p['burst']) / p['burst'] * 100
        for p in procs if p.get('predicted') and p['burst']
    ]
    return round(100 - sum(errors) / len(errors), 2) if errors else 0.0

def ml_reset():
    """Clear the EMA table (call between independent simulation runs)."""
    ema_table.clear()

# ─── Metric calculation ────────────────────────────────────────────────────────

def calc_metrics(procs):
    """Return a dict of average performance metrics for a completed schedule."""
    n     = len(procs)
    total = max(p['finish'] for p in procs)
    busy  = sum(p['burst']  for p in procs)
    return {
        'avg_wait'   : round(sum(p['wait']       for p in procs) / n, 2),
        'avg_tat'    : round(sum(p['turnaround'] for p in procs) / n, 2),
        'avg_resp'   : round(sum(p['response']   for p in procs) / n, 2),
        'throughput' : round(n / total, 4),
        'cpu_util'   : round(busy / total * 100, 1),
    }

# ─── Scheduling algorithms ─────────────────────────────────────────────────────

def fcfs(procs_in):
    """First Come First Served — non-preemptive, sorted by arrival time."""
    procs = deepcopy(procs_in)
    procs.sort(key=lambda p: p['arrival'])
    gantt, time = [], 0

    for p in procs:
        time          = max(time, p['arrival'])
        p['response'] = time - p['arrival']
        gantt.append({'pid': p['pid'], 'name': p['name'], 's': time, 'e': time + p['burst']})
        time          += p['burst']
        p['finish']    = time
        p['turnaround']= time - p['arrival']
        p['wait']      = p['turnaround'] - p['burst']

    return {
        'algo'   : 'FCFS',
        'gantt'  : gantt,
        'procs'  : procs,
        'metrics': calc_metrics(procs),
    }


def sjf(procs_in):
    """Shortest Job First — non-preemptive, picks shortest burst among arrived."""
    procs = deepcopy(procs_in)
    gantt = []
    done  = set()
    time  = 0

    while len(done) < len(procs):
        avail = [p for p in procs if p['pid'] not in done and p['arrival'] <= time]
        if not avail:
            time += 1
            continue
        p              = min(avail, key=lambda x: x['burst'])
        p['response']  = time - p['arrival']
        gantt.append({'pid': p['pid'], 'name': p['name'], 's': time, 'e': time + p['burst']})
        time           += p['burst']
        p['finish']     = time
        p['turnaround'] = time - p['arrival']
        p['wait']       = p['turnaround'] - p['burst']
        done.add(p['pid'])

    return {
        'algo'   : 'SJF (Non-Preemptive)',
        'gantt'  : gantt,
        'procs'  : procs,
        'metrics': calc_metrics(procs),
    }


def srtf(procs_in):
    """Shortest Remaining Time First — preemptive SJF, runs unit-by-unit."""
    procs = deepcopy(procs_in)
    for p in procs:
        p['rem']     = p['burst']
        p['started'] = False

    gantt = []
    time  = 0
    done  = set()

    while len(done) < len(procs):
        avail = [p for p in procs if p['arrival'] <= time and p['rem'] > 0]
        if not avail:
            time += 1
            continue

        p = min(avail, key=lambda x: x['rem'])

        # Record first-touch response time
        if not p['started']:
            p['started']  = True
            p['response'] = time - p['arrival']

        # Extend last gantt block if same process continues
        if gantt and gantt[-1]['pid'] == p['pid']:
            gantt[-1]['e'] += 1
        else:
            gantt.append({'pid': p['pid'], 'name': p['name'], 's': time, 'e': time + 1})

        p['rem'] -= 1
        time     += 1

        if p['rem'] == 0:
            p['finish']     = time
            p['turnaround'] = time - p['arrival']
            p['wait']       = p['turnaround'] - p['burst']
            done.add(p['pid'])

    return {
        'algo'   : 'SRTF (Preemptive SJF)',
        'gantt'  : gantt,
        'procs'  : procs,
        'metrics': calc_metrics(procs),
    }


def round_robin(procs_in, quantum):
    """Round Robin — each process gets at most 'quantum' units per turn."""
    procs = deepcopy(procs_in)
    for p in procs:
        p['rem']     = p['burst']
        p['started'] = False

    procs.sort(key=lambda p: p['arrival'])
    gantt  = []
    queue  = []
    in_q   = set()
    time   = 0
    done   = set()
    idx    = 0

    # Enqueue all processes that arrive at time 0
    while idx < len(procs) and procs[idx]['arrival'] == 0:
        queue.append(procs[idx])
        in_q.add(procs[idx]['pid'])
        idx += 1

    while len(done) < len(procs):
        if not queue:
            # Jump clock to the next arriving process
            time = procs[idx]['arrival']
            while idx < len(procs) and procs[idx]['arrival'] <= time:
                if procs[idx]['pid'] not in in_q:
                    queue.append(procs[idx])
                    in_q.add(procs[idx]['pid'])
                idx += 1

        p = queue.pop(0)

        if not p['started']:
            p['started']  = True
            p['response'] = time - p['arrival']

        exec_t = min(quantum, p['rem'])
        gantt.append({'pid': p['pid'], 'name': p['name'], 's': time, 'e': time + exec_t})
        time    += exec_t
        p['rem'] -= exec_t

        # Enqueue newly arrived processes after this slice
        while idx < len(procs) and procs[idx]['arrival'] <= time:
            if procs[idx]['pid'] not in in_q:
                queue.append(procs[idx])
                in_q.add(procs[idx]['pid'])
            idx += 1

        if p['rem'] == 0:
            p['finish']     = time
            p['turnaround'] = time - p['arrival']
            p['wait']       = p['turnaround'] - p['burst']
            done.add(p['pid'])
        else:
            queue.append(p)   # re-enqueue for next turn

    return {
        'algo'   : f'Round Robin (Quantum = {quantum})',
        'gantt'  : gantt,
        'procs'  : procs,
        'metrics': calc_metrics(procs),
        'quantum': quantum,
    }


def ml_sjf(procs_in):
    """
    ML-enhanced SJF using Exponential Moving Average (EMA) to predict burst times.
    Selects the process with the LOWEST predicted burst at each step.
    After execution, updates the EMA with the actual burst (learning).
    """
    procs   = deepcopy(procs_in)
    default = sum(p['burst'] for p in procs) // len(procs)  # fallback prediction

    # Assign predictions BEFORE scheduling starts
    for p in procs:
        p['predicted'] = ml_predict(p['pid'], default)

    gantt = []
    done  = set()
    time  = 0

    while len(done) < len(procs):
        avail = [p for p in procs if p['pid'] not in done and p['arrival'] <= time]
        if not avail:
            time += 1
            continue

        # Pick process with shortest PREDICTED burst
        p              = min(avail, key=lambda x: x['predicted'])
        p['response']  = time - p['arrival']
        gantt.append({'pid': p['pid'], 'name': p['name'], 's': time, 'e': time + p['burst']})
        time           += p['burst']          # execute actual burst
        p['finish']     = time
        p['turnaround'] = time - p['arrival']
        p['wait']       = p['turnaround'] - p['burst']
        done.add(p['pid'])
        ml_update(p['pid'], p['burst'])       # learn from actual

    acc = ml_accuracy(procs)

    # Build EMA model state for display
    ema_state = []
    for p in procs:
        ema_state.append({
            'pid'      : p['pid'],
            'name'     : p['name'],
            'actual'   : p['burst'],
            'predicted': p['predicted'],
            'next_ema' : round(ema_table.get(p['pid'], 0), 2),
        })

    return {
        'algo'     : 'ML-SJF (EMA Prediction)',
        'gantt'    : gantt,
        'procs'    : procs,
        'metrics'  : calc_metrics(procs),
        'ml_acc'   : acc,
        'ema_state': ema_state,
        'alpha'    : ALPHA,
    }


def compare_all(procs_in, quantum):
    """
    Run all five algorithms on the same process set and return a comparison table.
    ML state is reset before running ML-SJF so it always starts fresh in compare mode.
    """
    results = []

    for name, fn in [
        ('FCFS',    lambda p: fcfs(p)),
        ('SJF',     lambda p: sjf(p)),
        ('SRTF',    lambda p: srtf(p)),
        ('RR',      lambda p: round_robin(p, quantum)),
        ('ML-SJF',  lambda p: ml_sjf(p)),
    ]:
        ml_reset()          # fresh EMA for each isolated run
        res = fn(procs_in)
        results.append({
            'algo'   : name,
            'metrics': res['metrics'],
        })

    # Find best (minimum) avg_wait for highlighting
    best_wait = min(r['metrics']['avg_wait'] for r in results)
    for r in results:
        r['best_wait'] = (r['metrics']['avg_wait'] == best_wait)

    return results