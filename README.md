# SimScale Harmonic Response Example

A simple example demonstrating harmonic response analysis using the SimScale Python SDK and hard-coded simulation settings. Refer to other tutorials to see how dynamic BC and Material assignments can be done.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set your SimScale API key:
```bash
export SIMSCALE_API_KEY=your_api_key_here
```

3. Run the simulation:
```bash
python harmonic_response_tutorial.py
```

## What it does

- Imports a bracket geometry (STEP file)
- Applies steel material properties
- Sets up fixed supports and harmonic force load
- Runs harmonic response analysis (10-1000 Hz)
- Returns simulation results

The simulation runs in the cloud and results can be viewed in the SimScale platform.