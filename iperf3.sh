#!/bin/bash

# Exit on errors
set -euo pipefail

# Parse arguments
if [ $# -eq 5 ] ; then
    SERVER="$1"
    PORT="$2"
    SECS="$3"
    N="$4"
    LOG="$5"
else
    echo "usage:"
    echo "./iperf3.sh h1.ifne.eu 6050 86400 1 iperf3.log"
    echo "            server     port secs  n log"
    exit 1
fi

# Remove log file
rm -f $LOG

# Run iperf3
for i in `seq 1 $N` ; do
    date +'%Y-%m-%d %H:%M:%S' >> $LOG

    # -V : Verbose, so start timestamp is present in the log file (parsed by Python script)
    # -R : Reverse the direction of a test, so that the server sends data to the client
    #      because download bandwidth is usually higher than upload one
    # -b : Set minimal bitrate so footprint for long running test is minimal
    # -l : Needed for bitrates below 5M, otherwise "0.00 Bytes  0.00 bits/sec" lines are present
    #      https://github.com/esnet/iperf/issues/439
    iperf3 -c $SERVER -p $PORT -V -R -b 100K -l 0.1K -t $SECS >> $LOG

    echo >> $LOG
    echo >> $LOG
done
