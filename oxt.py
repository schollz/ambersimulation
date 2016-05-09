#!/usr/bin/env python

"""Changes the charge to 0 in prmtop"""

__author__   = "Zack Scholl"
__version__  = "March 30, 2016"

import sys
import os

def removeCharge():
	with open('FindCharge.in','w') as f:
		f.write("""Minimize
 &cntrl
  imin=1,
  ntx=1,
  irest=0,
  maxcyc=20,
  ncyc=10,
  ntpr=10,
  ntwx=0,
  cut=8.0,
 /
	""")

	if not os.path.isfile("prmtop.backup"):
		os.system('cp prmtop prmtop.backup')
		print("Original prmtop moved to prmtop.backup")

	if os.path.isfile("prmtop"):
		os.remove('prmtop')

	if os.path.isfile("prmtoptemp"):
		os.remove('prmtoptemp')

	a=open('prmtop.backup','r').read().splitlines()
	atomName = False
	atomCharge = False
	atomNum = 0
	atomNum1 = 0
	oxtNum = 0
	clNum = 0
	totalCharge = 0
	f = open('prmtoptemp','a')
	for line in a:
		if 'FLAG' in line:
			atomName = False
			atomCharge = False
		if 'ATOM_NAME' in line:
			atomName = True
		if 'CHARGE' in line:
			atomCharge = True
		if '%' in line:
			f.write(line+"\n")
			continue
		if atomName:
			for i in range(0,len(line),4):
				atomNum1 += 1
				if line[i:i+4]=="OXT ":
					# print(line[i:i+4],atomNum)
					oxtNum = atomNum1
					clNum = atomNum1 + 1
		if atomCharge:
			for i in range(0,len(line),16):
				atomNum += 1
				(num1,num2) = line[i:i+16].split("E")
				charge = float(num1)*10**float(num2)
				totalCharge += charge
				# Change carboxyl atom to zero charge
				if atomNum == oxtNum:
					totalCharge -= charge
					totalCharge += -0.0000001
					line=list(line)
					line[i:i+16] = " -0.00000010E+00"
					line = "".join(line)
		f.write(line+"\n")
	f.close()

	os.system('$AMBERHOME/bin/sander -O -i FindCharge.in -o 01_Min.out -p prmtoptemp -c inpcrd -r 01_Min.rst -inf 01_Min.mdinfo && cat 01_Min.out | grep charges > charge')
	inbalance = float(open('charge','r').read().split()[-1])
	print(inbalance)

	os.system('mv prmtoptemp prmtoptemp2')
	a=open('prmtoptemp2','r').read().splitlines()
	atomName = False
	atomCharge = False
	atomNum = 0
	atomNum1 = 0
	oxtNum = 0
	clNum = 0
	totalCharge = 0
	f = open('prmtoptemp','a')
	for line in a:
		if 'FLAG' in line:
			atomName = False
			atomCharge = False
		if 'ATOM_NAME' in line:
			atomName = True
		if 'CHARGE' in line:
			atomCharge = True
		if '%' in line:
			f.write(line+"\n")
			continue
		if atomName:
			for i in range(0,len(line),4):
				atomNum1 += 1
				if line[i:i+4]=="OXT ":
					# print(line[i:i+4],atomNum)
					oxtNum = atomNum1
					clNum = atomNum1 + 1
		if atomCharge:
			for i in range(0,len(line),16):
				atomNum += 1
				(num1,num2) = line[i:i+16].split("E")
				charge = float(num1)*10**float(num2)
				totalCharge += charge
				# Change the extra Cl- atom to be an effective carboxyl charge
				if atomNum == clNum:
					line=list(line)
					print(charge,inbalance)
					line[i:i+16] = '{0:>16.8E}'.format(charge - inbalance/0.05487781)
					line = "".join(line)
		f.write(line+"\n")
	f.close()

	os.system('$AMBERHOME/bin/sander -O -i FindCharge.in -o 01_Min.out -p prmtoptemp -c inpcrd -r 01_Min.rst -inf 01_Min.mdinfo && cat 01_Min.out | grep charges > charge')
	inbalance = float(open('charge','r').read().split()[-1])
	print("Current inbalance %f" % inbalance)

	os.system('mv prmtoptemp prmtop')
	os.remove('prmtoptemp2')
	os.remove('FindCharge.in')
	os.remove('charge')

	print(totalCharge*0.05487781,totalCharge, atomNum,atomNum1)
	os.system('diff prmtop prmtop.backup')
