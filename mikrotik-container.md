# iperf3 container on MikroTik
- [Docs](https://help.mikrotik.com/docs/display/ROS/Container)
- [Forum](https://forum.mikrotik.com/viewtopic.php?t=178383)

# Prerequisites
- [SSH access](maintenance/-/wikis/Wi-Fi#ssh-interface)
- RouterOS min version `v7.4beta4` ([upgrade]((https://help.mikrotik.com/docs/display/ROS/Upgrading+and+installation)) if needed)
- `container` extra package
  - Main package and extra packages can be found [here](https://mikrotik.com/download)
  - Check the installed packages
  ```
  /system/package/print
  Columns: NAME, VERSION
  # NAME       VERSION
  0 container  7.6    
  1 routeros   7.6
  ```
- Enabled Container mode
  - `/system/device-mode/update container=yes`
  - Press the reset button
  - Check the enabled container mode
  ```
  /system/device-mode/print
        mode: enterprise
    container: yes
  ```
- External disk is highly [recommended](https://help.mikrotik.com/docs/display/ROS/Container)
  - Mikrotik internally uses NAND flash memory with certain life time
  - It [may not be enough](https://forum.mikrotik.com/viewtopic.php?f=2&t=60963#p316934) for periodically written iperf3 log files:  
    "We rarely see anyone writing about bad sectors. You might be one of 2-3 people in the last few months, and mostly it's because of enabled debug logs to disk (which causes enormous amount of writes per minute)."
  ```
  /system/resource/print
  ...
           write-sect-total: 127643
                 bad-blocks: 0%
  ```

# Setup DNS
- [Doc](https://help.mikrotik.com/docs/display/ROS/DNS)
```
/ip/dns/set servers=1.1.1.1,8.8.8.8
/ip/dns/print
servers: 1.1.1.1,8.8.8.8
```

# Setup clock
- For correctly displaying parsed outage time intervals
- Use [NTP Client](https://ekonetcomp.blogspot.com/2018/11/ntp-client-setup.html)
```
/system/ntp/client/set enabled=yes servers=sk.pool.ntp.org
/system/ntp/client/print
     enabled: yes
        mode: unicast
     servers: sk.pool.ntp.org
         vrf: main
  freq-drift: 0 PPM
      status: synchronized
```


# Create bridge
```
# Add interface to the container
/interface/veth/add name=veth1 address=172.17.0.2/24 gateway=172.17.0.1

# Create a bridge
/interface/bridge/add name=dockers
/ip/address/add address=172.17.0.1/24 interface=dockers
/interface/bridge/port add bridge=dockers interface=veth1

# Setup NAT for outgoing traffic
/ip/firewall/nat/add chain=srcnat action=masquerade src-address=172.17.0.0/24

# Default gateway for the internet access has to be added because of our special setup
/ip/route/add gateway=192.168.88.1
/ip/route/print
Flags: D - DYNAMIC; A - ACTIVE; c, s, y - COPY
Columns: DST-ADDRESS, GATEWAY, DISTANCE
#     DST-ADDRESS      GATEWAY       DISTANCE
0  As 0.0.0.0/0        192.168.88.1         1
  DAc 172.17.0.0/24    dockers              0
  DAc 192.168.88.0/24  bridge               0
```

# Import Docker Image
- Save [iperf3-alpine image](https://hub.docker.com/r/taoyou/iperf3-alpine) for ARM as `*.tar`
```
docker pull taoyou/iperf3-alpine:v3.11 --platform linux/arm
docker save taoyou/iperf3-alpine -o iperf3-alpine.tar
```

- Upload image to the router via [FTP](https://git.ifne.eu/dnation/infra/maintenance/-/wikis/Wi-Fi#ssh-interface)
```
/file/print
Columns: NAME, TYPE, SIZE, CREATION-TIME
#  NAME                      TYPE       SIZE     CREATION-TIME       
0  iperf3-alpine.tar         .tar file  5.1MiB   jan/06/1970 17:35:28
```

# Create container
```
# Create
/container/add file=iperf3-alpine.tar interface=veth1 cmd="-c 46.4.77.52 -p 6050 -V -R -b 100K -l 1K -t 10" logging=yes

# status=extracting
/container/print
 0 name="37cbaf23-5fdf-47bb-a2c6-cdf24178ddcb" tag="" os="" arch="" interface=veth1 cmd="-c 46.4.77.52 -p 6050 -V -R -b 100K -l 1K -t 10" mounts="" 
   dns="" logging=yes status=extracting

 # status=stopped
/container/print
  0 name="37cbaf23-5fdf-47bb-a2c6-cdf24178ddcb" tag="taoyou/iperf3-alpine:v3.11" os="linux" arch="arm" interface=veth1 
   cmd="-c 46.4.77.52 -p 6050 -V -R -b 100K -l 1K -t 10" mounts="" dns="" logging=yes status=stopped 

/file/print
Columns: NAME, TYPE, SIZE, CREATION-TIME
#  NAME                                  TYPE             SIZE     CREATION-TIME       
1  37cbaf23-5fdf-47bb-a2c6-cdf24178ddcb  container store           jan/06/1970 17:40:40

# Start
/container/start 0
/log/print
 17:43:06 container,info,debug iperf 3.11
 ...
 17:43:14 container,info,debug [ ID] Interval           Transfer     Bitrate
 17:43:14 container,info,debug [  5]   0.00-1.00   sec  12.0 KBytes  98.3 Kbits/sec                  
 17:43:14 container,info,debug [  5]   1.00-2.00   sec  12.0 KBytes  98.3 Kbits/sec                  
...
17:43:16 container,info,debug iperf Done.
```

## Use volume mounts if you want to redirect logs to the file
```
# Create mount
/container/mounts/add name=iperf_log src=/iperf/log dst=/opt/log
/container/mounts/print
 0 name="iperf_log" src="/iperf/log" dst="/opt/log"

# Create container with mount
/container/add file=iperf3-alpine.tar interface=veth1 cmd="-R -c 46.4.77.52 -p 6052 -b 5M --logfile iperf3.log" mounts=iperf_log root-dir=/iperf/root
/container/set 0 workdir=/opt/log
/container/print
 0 name="750bde1e-8ab8-4af5-8484-bf68431243b9" tag="taoyou/iperf3-alpine:v3.11" os="linux" arch="arm" interface=veth1 cmd="-R -c 46.4.77.52 -p 6052 -b 5M --logfile iperf3.log" root-dir=/iperf/root 
   mounts=iperf_log dns="" workdir="/opt/log" status=stopped

# Start container
/container/start 0
/file/print
Columns: NAME, TYPE, SIZE, CREATION-TIME
#  NAME                      TYPE             SIZE     CREATION-TIME       
1  iperf/root                container store           jan/02/1970 10:54:15
4  iperf/log                 container store           jan/02/1970 10:57:24

# Download file via FTP
ftp 192.168.88.2
ftp> cd iperf/log
250 CWD command successful
ftp> ls
200 PORT command successful
150 Opening data connection
-rw-rw----   1 root     root         1191 Jan  2 10:57 iperf3.log
-rw-rw----   1 root     root           10 Jan  2 10:57 .type
226 Transfer complete
```
