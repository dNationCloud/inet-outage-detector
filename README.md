# dNation Internet Outage Detector

Ever wondered why your video calls sometimes suffer from poor voice/video quality? It may be related to reliability (not capacity) of your Internet connection.

We had this problem in my company for a while, main difficulty was that it happened only rarely. This project helps to detect Internet outages over a long period of time (e.g. 1 month) with minimal footprint. 

It uses [iperf3](https://github.com/esnet/iperf) running in special mode using minimal bandwidth so your other activities are not affected by the test. 

It helped us to detect defective Wi-Fi router and find out reliability of our Internet provider (99.98%).

# Running Test

## Server Side
```
# Connect to a server with iperf3 package installed
# This might be e.g. remote VM if you intend to test external connectivity
# or a machine in your local network if you want to test just your Wi-Fi router
ssh iperf3-server

# Optional: As we are going to run long lasting test, we probably want to use screen
screen

# Run iperf3 in server mode on port 6050, print statistics every 60 seconds (instead of every second; note we are not using these, just reducing printouts)
iperf3 -s -p 6050 -i 60

# Detach screen window so you can logout while iperf3 is still running
CTRL+a d
```

## Client Side
```
# Run test for 1 week
#
# Note 86400 secs (1 day) is the max enforced by iperf3 itself
# Use n > 1 for tests lasting more than 1 day
./iperf3.sh iperf3-server 6050 86400 7 `hostname`.`date +%Y-%m-%d-%H.%M.%S`.log
#           server        port secs  n log, e.g. hp.2022-12-23-17.41.16.log
```

# Evaluating Test

Parse log file produced in previous step:
```
./iperf3.py hp-dNation5G-2.2022-12-22-16.18.48.log
hp-dNation5G-2.2022-12-22-16.18.48.log: duration 1 day 1:21:30, 0 outages
```
## No Outages
Example above shows no outages, so no further action is needed - your Internet connection was reliable during whole test.

## Classifying Outages
Another example below shows several outages:
```
./iperf3.py hp-dNation5G-2.2023-01-05-23.15.26.log
hp-dNation5G-2.2023-01-05-23.15.26.log: duration 13 days 21:21:50, longest outage 354 secs, total 80 outages lasting 835 secs (0.06958%)
```

Use `-v` switch for printing detailed info including timestamps when outages happened, longest one marked with `*` character:
```
./iperf3.py -v hp-dNation5G-2.2023-01-05-23.15.26.log
hp-dNation5G-2.2023-01-05-23.15.26.log: duration 13 days 21:21:50, longest outage 354 secs, total 80 outages lasting 835 secs (0.06958%)
    2023-01-06 05:45:43 UTC, duration 0:00:01 (23417.00-23418.00)
    2023-01-06 17:05:59 UTC, duration 0:00:05 (64233.00-64238.00)
    2023-01-07 02:17:44 UTC, duration 0:00:01 (10938.00-10939.00)
    2023-01-07 02:53:44 UTC, duration 0:00:01 (13098.00-13099.00)
  * 2023-01-07 20:45:39 UTC, duration 0:05:54 (77413.00-77767.00)
    2023-01-07 22:09:35 UTC, duration 0:05:50 (82449.00-82799.00)
    2023-01-08 05:05:44 UTC, duration 0:00:01 (21017.00-21018.00)
    2023-01-08 11:45:46 UTC, duration 0:00:01 (45019.00-45020.00)
    2023-01-08 20:51:43 UTC, duration 0:00:01 (77776.00-77777.00)
    ...
```

There are 80 outages, however most of them are 1 second long. Let's filter them out so we can focus on longer ones:
```
./iperf3.py -v hp-dNation5G-2.2023-01-05-23.15.26.log | grep -v 'duration 0:00:01'
hp-dNation5G-2.2023-01-05-23.15.26.log: duration 13 days 21:21:50, longest outage 354 secs, total 80 outages lasting 835 secs (0.06958%)
    2023-01-06 17:05:59 UTC, duration 0:00:05 (64233.00-64238.00)
  * 2023-01-07 20:45:39 UTC, duration 0:05:54 (77413.00-77767.00)
    2023-01-07 22:09:35 UTC, duration 0:05:50 (82449.00-82799.00)
    2023-01-09 08:16:49 UTC, duration 0:00:03 (32482.00-32485.00)
    ...
```

Two long outages happened at 2023-01-07, both almost 6 minutes long.  An outage might have multiple causes, e.g.:
1. Connection problems of your Internet provider to outside world where your iperf3 server is running
2. Remote iperf3 server machine connection problems which are outside of control of your Internet provider

To distinguish between these causes we need to run test again, this time for a long period of time while running [dNation Ping](https://dnation.cloud/products/ping/) in parallel. In our example we already did so, so we can use dNation Ping to display relevant time period:

1) Go to http://localhost:3001/

2) Use following credentials to login:  
User: `admin`  
Password: `tmp`

3) Display graph for day 2023-01-07, time interval 20:40-22:30 (all timestamps are in UTC)
![outage](./doc/outage.png)

Indeed, we can see that at:
* 20:45:45 We haven't received a response from most of the servers being pinged
* 20:46:00 None of the servers responded
* 22:09:45 Another outage began

Suddenly we can't ping any remote server, so it is very likely that an outage was caused by our Internet provider.

Note there is still an option that machine we are using for measurements completely lost connection, but that would by recorded in `/var/log/syslog`. However, to avoid any doubt, you can add some local server (e.g. a printer, 192.168.1.10 or similar) to list of machines being pinged.

Also note dNation Ping by default uses 15 seconds granularity, so shorter outages will be not shown. It is possible to decrease this interval however more bandwidth will be used. A measurement consist of 2 ICMP packets (ping, pong) targeting each server, each of them 1500 bytes long (MTU), so for 12 servers above it would be: `2*12*1500 = 36000 / 1024 = 35.16 KBytes/s`

## Additional Test Scenarios

Following use cases were considered:

1. Testing external connectivity: see description above
1. Testing local network elements, e.g. two Wi-Fi routers located in different rooms  
* Test is ran on both Wi-Fi routers each connecting to the same local iperf3 server but different port (e.g. 6050 and 6051)
* Real outages are those when one test reports outage while the other doesn't, so Wi-Fi router reporting an outage is defective

# Open Tasks
1. Publish to GitHub
1. Re-do summary as described is output.ods
1. New switch `--min-duration 10`
1. Support MatterMost notifications
1. `docker-compose build` - so image for MikroTik can be easily created
1. Support stdin to reduce HDD footprint - no need for temporary *.log file
