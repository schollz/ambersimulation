# Setup

```bash
git clone https://github.com/schollz/ambersimulation.git 'mynewsimulation'      (to download the software into a directory)
cd mynewsimulation
python setup.py        (to setup the simulation)
nohup python simulate.py &             (to start the simulation)
tail -f log   (to watch the output)
```

Basically what it first does a minimization/heating/preproduction/production for 2 nanoseconds and then uses the last frame to generate a new simulation. The second simulation regenerates the waterbox and does min/heat/preproduction/production for the specified amount of time (specified by setup.py).

