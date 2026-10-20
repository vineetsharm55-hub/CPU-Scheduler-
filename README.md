# CPU Scheduler Simulator

A Flask web app that simulates classic CPU scheduling algorithms and compares them side by side, including an experimental **ML-SJF** scheduler that predicts burst times with an exponential moving average.

## Algorithms

| Algorithm | Type | Notes |
|---|---|---|
| **FCFS** | Non-preemptive | First come, first served |
| **SJF** | Non-preemptive | Shortest job first |
| **SRTF** | Preemptive | Shortest remaining time first |
| **Round Robin** | Preemptive | Configurable time quantum (default 3) |
| **ML-SJF** | Non-preemptive | Picks the process with the lowest *predicted* burst, then learns from the actual burst |

**How ML-SJF works:** each process gets a predicted burst from an exponential moving average (EMA, smoothing factor α = 0.65). After a process runs, the EMA is updated with its actual burst. Unseen processes fall back to the average burst of the input set. The app also reports prediction accuracy.

## What you get

- Gantt chart data for each run
- Per-process arrival, burst, waiting, turnaround and response times
- Average metrics for every algorithm
- A comparison of all five algorithms on the same process set, highlighting the lowest average waiting time

## Project structure

```
├── app.py          # Flask backend: parses input, runs the chosen algorithm, returns JSON
├── scheduler.py    # All scheduling algorithms and the EMA predictor
└── templates/
    └── index.html  # Single-page frontend
```

## API

**`POST /run`**

```json
{
  "algorithm": "fcfs | sjf | srtf | rr | mlsjf",
  "quantum": 3,
  "processes": [
    { "name": "P1", "arrival": 0, "burst": 5 },
    { "name": "P2", "arrival": 1, "burst": 3 }
  ]
}
```

Returns the Gantt chart, per-process table and average metrics.

**`POST /compare`** takes the same body (without `algorithm`) and returns the metrics of all five algorithms.

## Getting started

```bash
git clone https://github.com/vineetsharm55-hub/CPU-Scheduler-.git
cd CPU-Scheduler-
pip install flask
python app.py
```

Then open http://127.0.0.1:5000 in your browser.

## Tech stack

Python, Flask, HTML/JS frontend

## Author

[@vineetsharm55-hub](https://github.com/vineetsharm55-hub)
