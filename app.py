# app.py
# Flask backend — receives process data from the frontend,
# runs the selected scheduling algorithm, and returns JSON results.

from flask import Flask, render_template, request, jsonify
from scheduler import (
    fcfs, sjf, srtf, round_robin, ml_sjf,
    compare_all, ml_reset
)

app = Flask(__name__)


# ─── Helper ───────────────────────────────────────────────────────────────────

def parse_processes(data):
    """
    Convert the JSON body sent from the frontend into the internal process list.
    Each process gets a unique PID starting at 1001.
    """
    procs = []
    for i, item in enumerate(data['processes']):
        procs.append({
            'pid'       : 1001 + i,
            'name'      : item['name'].strip() or f'P{i+1}',
            'arrival'   : int(item['arrival']),
            'burst'     : int(item['burst']),
            'predicted' : 0.0,   # filled by ml_sjf if needed
            'wait'      : 0,
            'turnaround': 0,
            'response'  : 0,
            'finish'    : 0,
        })
    return procs


def format_result(res):
    """
    Convert the raw result dict from a scheduler function into a clean JSON
    structure the frontend can render directly.
    """
    out = {
        'algo'   : res['algo'],
        'gantt'  : res['gantt'],
        'metrics': res['metrics'],
        'table'  : [],
    }

    show_ml = 'ema_state' in res   # only ML-SJF has this

    for p in res['procs']:
        row = {
            'pid'       : p['pid'],
            'name'      : p['name'],
            'arrival'   : p['arrival'],
            'burst'     : p['burst'],
            'wait'      : p['wait'],
            'turnaround': p['turnaround'],
            'response'  : p['response'],
        }
        if show_ml:
            # Find the matching EMA row for predicted / error
            ema_row = next((e for e in res['ema_state'] if e['pid'] == p['pid']), None)
            if ema_row:
                pred = ema_row['predicted']
                err  = round(abs(pred - p['burst']) / p['burst'] * 100, 1) if p['burst'] else 0
                row['predicted'] = pred
                row['error_pct'] = err
                row['next_ema']  = ema_row['next_ema']
        out['table'].append(row)

    if show_ml:
        out['ml_acc']   = res.get('ml_acc', 0)
        out['alpha']    = res.get('alpha', 0.65)
        out['ema_state']= res.get('ema_state', [])

    if 'quantum' in res:
        out['quantum'] = res['quantum']

    return out


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    """Serve the single-page frontend."""
    return render_template('index.html')


@app.route('/run', methods=['POST'])
def run():
    """
    POST /run
    Body: { "algorithm": "fcfs"|"sjf"|"srtf"|"rr"|"mlsjf",
            "quantum": 3,
            "processes": [ { "name", "arrival", "burst" }, … ] }
    Response: JSON result ready for the frontend to display.
    """
    try:
        data    = request.get_json()
        algo    = data.get('algorithm', 'fcfs').lower()
        quantum = int(data.get('quantum', 3))
        procs   = parse_processes(data)

        if not procs:
            return jsonify({'error': 'No processes provided.'}), 400

        ml_reset()   # fresh EMA state for each independent run

        # Dispatch to the correct algorithm
        if algo == 'fcfs':
            res = fcfs(procs)
        elif algo == 'sjf':
            res = sjf(procs)
        elif algo == 'srtf':
            res = srtf(procs)
        elif algo == 'rr':
            res = round_robin(procs, quantum)
        elif algo == 'mlsjf':
            res = ml_sjf(procs)
        else:
            return jsonify({'error': f'Unknown algorithm: {algo}'}), 400

        return jsonify({'result': format_result(res)})

    except ValueError as ve:
        return jsonify({'error': f'Invalid input value: {ve}'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/compare', methods=['POST'])
def compare():
    """
    POST /compare
    Body: { "quantum": 3,
            "processes": [ { "name", "arrival", "burst" }, … ] }
    Response: JSON array of per-algorithm metric rows.
    """
    try:
        data    = request.get_json()
        quantum = int(data.get('quantum', 3))
        procs   = parse_processes(data)

        if not procs:
            return jsonify({'error': 'No processes provided.'}), 400

        results = compare_all(procs, quantum)
        return jsonify({'comparison': results, 'quantum': quantum})

    except ValueError as ve:
        return jsonify({'error': f'Invalid input value: {ve}'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == '__main__':
    app.run(debug=True)