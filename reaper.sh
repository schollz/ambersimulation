#!/bin/bash
while :
do
	PROCESS_FOUND=`ps -ef|grep 'simulate.py production'|grep -v grep`
	if [ "$PROCESS_FOUND" = "" ]
	then
		echo "$(date && tail simulation.log)" | mailx -s "STOPPED $(pwd)" zack.scholl@gmail.com
		break
	fi
	sleep 60
done


