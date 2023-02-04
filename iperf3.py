#!/usr/bin/python3

import sys
import re
from datetime import datetime, timedelta, timezone
import logging


def proc_file(fn: str, verbose: bool):
    # Intentionally no exception are caught
    f = open(fn, "r")

    # Number of currently processed line
    n: int = 0

    # Total number of seconds when test ran
    total_secs: float = 0

    # Start of the test (written by iperf3.sh, e.g. 2022-12-04 07:00:50)
    #
    # Not using None because mypy would complain
    # error: Incompatible types in assignment (expression has type "None", variable has type "float")
    #
    # Tried:
    # from typing import Optional
    # test_start: Optional[float] = None
    # But that leads to re-factoring of several code blocks below (e.g. logging.debug()) for no obvious benefit
    test_start: float = -1

    # Last seen end value, column "Interval" 2nd value
    last_end: float = -1

    # Found outages
    outages: list = []

    # Start of currently examined outage
    outage_start: float = -1

    while True:
        # Read next line
        line: str = f.readline()
        if not line:
            break
        line = line.strip()
        n += 1

        # Look for lines describing how test proceeds
        # This type of line is most common, searching for it as a first choice so there are no unnecessary
        # re.match() calls
        #
        # New iperf3 (Ubuntu 20.04) output contains 4 columns:
        # [ ID] Interval           Transfer     Bitrate
        # [  7]   0.00-1.00   sec   592 KBytes  4.85 Mbits/sec
        #
        # Old iperf3 (Ubuntu 16.04) output contains 6 columns:
        # [ ID] Interval            Transfer    Bandwidth       Retr  Cwnd
        # [  4]   0.00-1.00   sec   614 KBytes  5.03 Mbits/sec    0   73.5 KBytes
        #
        # Supporting both output formats.
        #
        # Ignore summary lines:
        # [  7]   0.00-22933.71 sec  0.00 Bytes   0.00 bits/sec    sender
        # [  7]   0.00-22933.71 sec  13.3 GBytes  5.00 Mbits/sec   receiver
        m_str = re.match(r"^\[.+\] +([0-9.]+)-([0-9.]+).*sec +([0-9.]+) .*Bytes.*bits\/sec", line)
        if m_str:
            # Ignore summary lines
            if line.endswith("sender") or line.endswith("receiver"):
                continue

            # Store parsed values
            tmp: list = list(map(float, m_str.groups()))
            start: float = tmp[0]
            end: float = tmp[1]
            transfer: float = tmp[2]

            # State machine
            if outage_start == -1:
                # No outage is currently examined
                if transfer == 0.0:
                    # Found start of outage
                    outage_start = start
            else:
                # An outage is currently examined
                if transfer != 0.0:
                    # Found end of outage, store it
                    logging.debug("file '%s', outage found: %d.00-%d.00 %d secs" % (fn, outage_start, last_end, last_end - outage_start))
                    outages.append([test_start, outage_start, last_end, last_end - outage_start])

                    # Outage recorded, reset values so next one can be processed
                    outage_start = -1

            # Current value are now last seen values
            last_end = end
            continue

        # Look for start of the test
        # Time: Mon, 19 Dec 2022 18:59:15 GMT
        m_str = re.match(r"^Time: ..., [0-9]{1,2} ... [0-9]{4} [0-9]{2}:[0-9]{2}:[0-9]{2} GMT$", line)
        if m_str:
            # Neither "%Z" or "%z" instead of "GMT" worked properly
            # https://9to5answer.com/python-strptime-and-timezones, see Solution 3
            dt = datetime.strptime(m_str[0], "Time: %a, %d %b %Y %H:%M:%S GMT").replace(tzinfo=timezone.utc)
            logging.debug("\n\nFound timestamp on line %d: %s" % (n, dt.strftime("%Y-%m-%d %H:%M:%S %Z")))
            test_start = dt.timestamp()
            continue

        # Look for end of test
        if line.startswith("- - -"):
            if outage_start != -1:
                # End of test occurred while an outage is examined, so outage ends here
                logging.debug("file '%s', outage found: %d.00-%d.00 %d secs" % (fn, outage_start, last_end, last_end - outage_start))
                outages.append([test_start, outage_start, last_end, last_end - outage_start])

            # Update values
            total_secs += last_end

            # Reset values so next test can be processed
            test_start = last_end = outage_start = -1
            continue

    f.close()

    # Check whether end of file occurred before end of test ("- - -") found
    # It happens when test is prematurely terminated (e.g. by CTRL+c)
    if last_end != -1:
        # Update values
        total_secs += last_end

        # Check whether an outage is being examined
        if outage_start != -1:
            logging.debug("file '%s', outage found: %d.00-%d.00 %d secs" % (fn, outage_start, last_end, last_end - outage_start))
            outages.append([test_start, outage_start, last_end, last_end - outage_start])

    logging.debug("\n\nfile '%s', outages: %s" % (fn, outages))
    logging.debug("file '%s', lines processed: %d" % (fn, n))

    # Print summary
    print("%s: duration %s" % (fn, str(timedelta(seconds=total_secs)).replace(", ", " ")), end=", ")
    if len(outages) == 0:
        print("0 outages")
    else:
        # Find outage with maximum duration
        outage_max: list = max(outages, key=lambda outage: outage[3])

        # Compute total duration of all outages
        outages_dur = sum([outage[3] for outage in outages])

        print("longest outage %d secs, total %d outages lasting %d secs (%.5f%%)" % (
            outage_max[3], len(outages),
            outages_dur,
            outages_dur / total_secs * 100
        ))

        if verbose:
            for outage in outages:
                prefix: str = "   "
                if outage[3] == outage_max[3]:
                    prefix = "  *"
                print("%s %s, duration %s (%d.00-%d.00)" % (
                    prefix,
                    datetime.fromtimestamp(outage[0]+outage[1])
                            .replace(tzinfo=timezone.utc)
                            .strftime("%Y-%m-%d %H:%M:%S %Z")
                    if outage[0] != -1 else "<Unknown>",
                    str(timedelta(seconds=outage[3])).replace(", ", " "), outage[1], outage[2]
                ))


if __name__ == "__main__":
    # Set format for debug messages
    # logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")

    # Check arguments
    verbose = False
    if len(sys.argv) <= 1:
        print("usage: %s [-v] iperf3.log [iperf3-2.log ...]" % sys.argv[0])
        exit(1)
    elif sys.argv[1] == "-v":
        verbose = True
        fns = sys.argv[2:]
    else:
        fns = sys.argv[1:]

    # Process files provided on a command line
    for fn in fns:
        proc_file(fn, verbose)
