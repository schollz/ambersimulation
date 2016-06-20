#!/usr/bin/env python

"""AMBER simulations"""

__author__ = "Zack Scholl"
__copyright__ = "Copyright 2016, Duke University"
__credits__ = ["Zack Scholl"]
__license__ = "None"
__version__ = "0.2"
__maintainer__ = "Zack Scholl"
__email__ = "zns@duke.edu"
__status__ = "Production"

import time
import json
import os
import sys
import shutil
import subprocess
import shlex
import logging
import glob

# set up logging to file - see previous section for more details
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                    datefmt='%m-%d %H:%M:%S',
                    filename='log',
                    filemode='w')
# define a Handler which writes INFO messages or higher to the sys.stderr
console = logging.StreamHandler()
console.setLevel(logging.INFO)
# set a format which is simpler for console use
formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
# tell the handler to use this format
console.setFormatter(formatter)
# add the handler to the root logger
logging.getLogger('').addHandler(console)

baseDir = os.getcwd()

from oxt import *

params = json.load(open('params.json', 'r'))


def dumpPDBs():
    logger = logging.getLogger("dumpPDBs")

    logger.info("Reimaging...")
    cmd = "%(amber)s/bin/cpptraj -p %(cwd)s/prmtop.backup -i %(cwd)s/reimage.in" % {
        'cwd': os.getcwd(), 'amber': os.environ['AMBERHOME']}
    logger.debug("Running command '" + cmd + "'")
    proc = subprocess.Popen(shlex.split(cmd), shell=False)
    proc.wait()
    logger.info("Reimaging finished.")

    with open("dump.tcl", "w") as f:
        f.write("""mol new prmtop.backup type parm7
mol addfile 03_Prod_reimage.mdcrd type crdbox waitfor -1

file mkdir pdbs/
set nf [molinfo top get numframes]
for {set i 0} {$i < $nf} {incr i} {
set a [atomselect top "all" frame $i]
$a writepdb pdbs/$i.pdb
}

quit
""")
    cmd = "vmd -dispdev text -e dump.tcl"
    logger.debug("Running command '" + cmd + "'")
    proc = subprocess.Popen(shlex.split(cmd), shell=False)
    proc.wait()
    # Dump all to one file
    os.chdir("pdbs")
    os.system("cat `ls -tr` > ../all.pdb")
    os.chdir("../")


def collapse():
    logger = logging.getLogger("collapse-setup")

    logger.info("Creating NOH version from linear PDB")
    with open('vmddump', 'w') as f:
        f.write("""mol new fullSequenceLinear.pdb
set a [atomselect top noh]
$a writepdb startingNoh.pdb
quit""")
    cmd = "vmd -dispdev text -e vmddump"
    proc = subprocess.Popen(shlex.split(cmd), shell=False)
    proc.wait()
    os.remove("vmddump")

    newFolder = 'collapse'
    logger.info("Creating prmtop/inpcrd from sequence")
    tleapConf = """source leaprc.ff14SB
loadAmberParams frcmod.ionsjc_tip3p
mol = loadpdb ../startingNoh.pdb
solvatebox mol TIP3PBOX 15.0
addions mol Na+ 0
addions mol Cl- 0
addions mol Cl- 1
saveamberparm mol prmtop inpcrd
quit"""
    try:
        shutil.rmtree(newFolder)
    except:
        pass
    os.mkdir(newFolder)
    os.chdir(newFolder)
    with open("tleap.foo", "w") as f:
        f.write(tleapConf)
    cmd = "tleap -f tleap.foo"
    logger.debug("Running command '" + cmd + "'")
    proc = subprocess.Popen(shlex.split(cmd), shell=False)
    proc.wait()
    os.remove("tleap.foo")

    if params['removeOxt']:
        logger.info("Removing OXT charge...")
        removeCharge()
    else:
        os.system('cp prmtop prmtop.backup')

    os.system("%(amber)s/bin/ambpdb -p prmtop < inpcrd > startingConfiguration.pdb" %
              {'amber': os.environ['AMBERHOME']})

    with open("reimage.in", "w") as f:
        f.write("""trajin 03_Prod.mdcrd
trajout 03_Prod_reimage.mdcrd
center :1-%(last)s
image familiar
go""" % {'last': str(params['numResidues'])})

    runSimulation(newFolder)


def runSimulation(nn):
    logger = logging.getLogger(nn + '-simulation')

    # implementing hydrogen reweighting
    if params['reweighting']:
        logger.info("Re-weighting hydrogens")
        reweightHydrogens()

    logger.info("Minimizing...")
    os.system('cp ../01_Min.in ./')
    cmd = "%(amber)s/bin/pmemd.cuda -O -i %(cwd)s/01_Min.in -o %(cwd)s/01_Min.out -p %(cwd)s/prmtop -c %(cwd)s/inpcrd -r %(cwd)s/01_Min.rst -inf %(cwd)s/01_Min.mdinfo" % {
        'cwd': os.getcwd(), 'amber': os.environ['AMBERHOME']}
    proc = subprocess.Popen(shlex.split(cmd), shell=False, env=dict(
        os.environ, CUDA_VISIBLE_DEVICES=params['cudaDevice']))
    proc.wait()

    logger.info("Heating to %d..." % params['temp'])
    os.system('cp ../02_Heat.in ./')
    cmd = "%(amber)s/bin/pmemd.cuda -O -i %(cwd)s/02_Heat.in -o %(cwd)s/02_Heat.out -p %(cwd)s/prmtop -c %(cwd)s/01_Min.rst -r %(cwd)s/02_Heat.rst -x %(cwd)s/02_Heat.mdcrd -inf %(cwd)s/02_Heat.mdinfo" % {
        'cwd': os.getcwd(), 'amber': os.environ['AMBERHOME']}
    logger.debug("Running command '" + cmd + "'")
    proc = subprocess.Popen(shlex.split(cmd), shell=False, env=dict(
        os.environ, CUDA_VISIBLE_DEVICES=params['cudaDevice']))
    proc.wait()

    logger.info("Pre-production simulation...")
    os.system('cp ../025_PreProd.in ./')
    cmd = "%(amber)s/bin/pmemd.cuda -O -i %(cwd)s/025_PreProd.in -o %(cwd)s/025_PreProd.out -p %(cwd)s/prmtop -c %(cwd)s/02_Heat.rst -r %(cwd)s/025_PreProd.rst -x %(cwd)s/025_PreProd.mdcrd -inf %(cwd)s/025_PreProd.mdinfo" % {
        'cwd': os.getcwd(), 'amber': os.environ['AMBERHOME']}
    logger.debug("Running command '" + cmd + "'")
    proc = subprocess.Popen(shlex.split(cmd), shell=False, env=dict(
        os.environ, CUDA_VISIBLE_DEVICES=params['cudaDevice']))
    proc.wait()
    logger.info("Simulation finished.")

    logger.info("Production simulation...")
    os.system('cp ../03_Prod.in ./')
    if nn == 'collapse':
        os.system('cp ../03_Prod_collapse.in ./03_Prod.in')
    cmd = "%(amber)s/bin/pmemd.cuda -O -i %(cwd)s/03_Prod.in -o %(cwd)s/03_Prod.out -p %(cwd)s/prmtop -c %(cwd)s/025_PreProd.rst -r %(cwd)s/03_Prod.rst -x %(cwd)s/03_Prod.mdcrd -inf %(cwd)s/03_Prod.mdinfo" % {
        'cwd': os.getcwd(), 'amber': os.environ['AMBERHOME']}
    logger.debug("Running command '" + cmd + "'")
    proc = subprocess.Popen(shlex.split(cmd), shell=False, env=dict(
        os.environ, CUDA_VISIBLE_DEVICES=params['cudaDevice']))
    # Poll process until finished
    step = 0
    while True:
        if proc.poll() != None:
            break
        time.sleep(30)
        step += 1
        if step % 1 == 0:
            os.system(
                "grep 'ns/day' %(cwd)s/03_Prod.mdinfo | tail -n 1 | awk '{print $4}' > foo1" % {'cwd': os.getcwd()})
            os.system(
                """grep 'time rem' %(cwd)s/03_Prod.mdinfo | tail -n 1 | awk '{print $5" "$6}' > foo2"""  % {'cwd': os.getcwd()})
            speed = open('foo1', 'r').read().strip()
            timeleft = open('foo2', 'r').read().strip()
            logger.debug("ns/day: %s, time left: %s" % (speed, timeleft))
            os.remove('foo1')
            os.remove('foo2')
        if step % 10 == 0:
            dumpPDBs()
    logger.info("Simulation finished.")

    logger.info("Dumping to pdbs/")
    dumpPDBs()  # dump.py
    logger.info("Finished dumping pdbs.")


def reweightHydrogens():
    os.system('cp prmtop prmtop.backup')
    os.system('cp inpcrd inpcrd.backup')
    tleapConf = """setOverwrite true
HMassRepartition 3
outparm prmtop inpcrd
go"""
    with open("parmed.foo", "w") as f:
        f.write(tleapConf)
    cmd = "parmed.py -p prmtop -c inpcrd -O -i parmed.foo"
    proc = subprocess.Popen(shlex.split(cmd), shell=False)
    proc.wait()
    os.remove("parmed.foo")


def production():
    logger = logging.getLogger('production-setup')
    os.chdir(baseDir)
    newFolder = 'production'
    try:
        shutil.rmtree(newFolder)
    except:
        pass
    os.mkdir(newFolder)
    os.chdir(newFolder)
    startPDB = ""
    files = glob.glob("../collapse/pdbs/*.pdb")
    maxNum = 0
    for f in files:
        if "all.pdb" in f:
            continue
        num = int(f.split("/")[-1].replace(".pdb", ""))
        if num > maxNum:
            maxNum = num
    startPDB = "%d.pdb" % maxNum
    os.system('cp ../collapse/pdbs/%s ./' % (startPDB))

    logger.info("Starting PDB is %s" % (startPDB))

    with open('vmddump', 'w') as f:
        f.write("""mol new %(startPDB)s
set a [atomselect top "protein and noh"]
$a writepdb collapsed.pdb
quit""" % {'startPDB': startPDB})
    cmd = "vmd -dispdev text -e vmddump"
    proc = subprocess.Popen(shlex.split(cmd), shell=False)
    proc.wait()
    os.remove("vmddump")

    logger.info("Creating prmtop/inpcrd from sequence")
    tleapConf = """source leaprc.ff14SB
loadAmberParams frcmod.ionsjc_tip3p
mol = loadpdb collapsed.pdb
solvatebox mol TIP3PBOX %s
addions mol Na+ 0
addions mol Cl- 0
addions mol Cl- 1
saveamberparm mol prmtop inpcrd
quit""" % (str(params['boxSize']))
    with open("tleap.foo", "w") as f:
        f.write(tleapConf)
    cmd = "tleap -f tleap.foo"
    logger.debug("Running command '" + cmd + "'")
    proc = subprocess.Popen(shlex.split(cmd), shell=False)
    proc.wait()
    os.remove("tleap.foo")


    # Instead of removing OXT, add NHE onto your structure
    # if params['removeOxt']:
    #     logger.info("Removing OXT charge...")
    #     removeCharge()
    # else:
    #     os.system('cp prmtop prmtop.backup')

    os.system("%(amber)s/bin/ambpdb -p prmtop < inpcrd > startingConfiguration.pdb" %
              {'amber': os.environ['AMBERHOME']})

    with open("reimage.in", "w") as f:
        f.write("""trajin 03_Prod.mdcrd
trajout 03_Prod_reimage.mdcrd
center :1-%(last)s
image familiar
go""" % {'last': str(params['numResidues'])})

    runSimulation('production')

if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == 'production':
        production()
    elif len(sys.argv) == 2 and sys.argv[1] == 'collapse':
        collapse()
    else:
        collapse()
        production()
