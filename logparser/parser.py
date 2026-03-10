import re
import time
import os
from collections import defaultdict
from prometheus_client import start_http_server, Gauge, Counter, REGISTRY, PROCESS_COLLECTOR, PLATFORM_COLLECTOR

REGISTRY.unregister(PROCESS_COLLECTOR)
REGISTRY.unregister(PLATFORM_COLLECTOR)

# Gauges for different time windows
bytes_recv_1h  = Gauge('fortigate_bytes_received_1h',  'Bytes received in last 1h',  ['srcmac','srcname','app','appcat'])
bytes_sent_1h  = Gauge('fortigate_bytes_sent_1h',      'Bytes sent in last 1h',      ['srcmac','srcname','app','appcat'])
sessions_1h    = Gauge('fortigate_sessions_1h',        'Sessions in last 1h',        ['srcmac','srcname','app','appcat'])

bytes_recv_24h = Gauge('fortigate_bytes_received_24h', 'Bytes received in last 24h', ['srcmac','srcname','app','appcat'])
bytes_sent_24h = Gauge('fortigate_bytes_sent_24h',     'Bytes sent in last 24h',     ['srcmac','srcname','app','appcat'])
sessions_24h   = Gauge('fortigate_sessions_24h',       'Sessions in last 24h',       ['srcmac','srcname','app','appcat'])

# Counters for timeseries rate() calculations
bytes_recv_counter = Counter('fortigate_bytes_received_total', 'Bytes received counter', ['srcmac','srcname','app','appcat'])
bytes_sent_counter = Counter('fortigate_bytes_sent_total',     'Bytes sent counter',     ['srcmac','srcname','app','appcat'])
sessions_counter   = Counter('fortigate_sessions_total',       'Sessions counter',       ['srcmac','srcname','app','appcat'])

# In-memory event log: list of (timestamp, srcmac, srcname, app, appcat, rcvd, sent)
events = []

def parse_line(line):
    fields = {}
    for match in re.finditer(r'(\w+)="?([^"\s]+)"?', line):
        fields[match.group(1)] = match.group(2)
    return fields

def rebuild_gauges():
    now = time.time()
    cutoff_1h  = now - 3600
    cutoff_24h = now - 86400

    # Remove events older than 24h
    while events and events[0][0] < cutoff_24h:
        events.pop(0)

    # Aggregate
    agg_1h  = defaultdict(lambda: [0, 0, 0])
    agg_24h = defaultdict(lambda: [0, 0, 0])

    for ts, srcmac, srcname, app, appcat, rcvd, sent in events:
        key = (srcmac, srcname, app, appcat)
        agg_24h[key][0] += rcvd
        agg_24h[key][1] += sent
        agg_24h[key][2] += 1
        if ts >= cutoff_1h:
            agg_1h[key][0] += rcvd
            agg_1h[key][1] += sent
            agg_1h[key][2] += 1

    # Clear and reset all gauges
    bytes_recv_1h._metrics.clear()
    bytes_sent_1h._metrics.clear()
    sessions_1h._metrics.clear()
    bytes_recv_24h._metrics.clear()
    bytes_sent_24h._metrics.clear()
    sessions_24h._metrics.clear()

    for key, (rcvd, sent, sess) in agg_1h.items():
        srcmac, srcname, app, appcat = key
        bytes_recv_1h.labels(srcmac=srcmac, srcname=srcname, app=app, appcat=appcat).set(rcvd)
        bytes_sent_1h.labels(srcmac=srcmac, srcname=srcname, app=app, appcat=appcat).set(sent)
        sessions_1h.labels(srcmac=srcmac, srcname=srcname, app=app, appcat=appcat).set(sess)

    for key, (rcvd, sent, sess) in agg_24h.items():
        srcmac, srcname, app, appcat = key
        bytes_recv_24h.labels(srcmac=srcmac, srcname=srcname, app=app, appcat=appcat).set(rcvd)
        bytes_sent_24h.labels(srcmac=srcmac, srcname=srcname, app=app, appcat=appcat).set(sent)
        sessions_24h.labels(srcmac=srcmac, srcname=srcname, app=app, appcat=appcat).set(sess)

def tail_file(filepath):
    with open(filepath, 'r') as f:
        f.seek(0, 2)
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.1)
                continue
            yield line

def main():
    log_file = '/var/log/fortigate.log'
    start_http_server(9200)
    print('Metrics server started on port 9200')
    print(f'Tailing {log_file}')

    last_rebuild = time.time()

    for line in tail_file(log_file):
        try:
            if 'rcvdbyte' not in line:
                continue
            f = parse_line(line)

            # Only count WAN-bound forwarded traffic to avoid double-counting
            subtype = f.get('subtype', '')
            dstintf = f.get('dstintf', '')
            if subtype != 'forward' or dstintf != 'wan':
                continue

            srcmac  = f.get('srcmac', 'unknown')
            srcname = f.get('srcname', 'unknown')
            app     = f.get('app', 'unknown')
            appcat  = f.get('appcat', 'unknown')
            rcvd    = int(f.get('rcvddelta', f.get('rcvdbyte', 0)))
            sent    = int(f.get('sentdelta', f.get('sentbyte', 0)))

            if not srcmac or srcmac == 'unknown':
                continue

            events.append((time.time(), srcmac, srcname, app, appcat, rcvd, sent))
            bytes_recv_counter.labels(srcmac=srcmac, srcname=srcname, app=app, appcat=appcat).inc(rcvd)
            bytes_sent_counter.labels(srcmac=srcmac, srcname=srcname, app=app, appcat=appcat).inc(sent)
            sessions_counter.labels(srcmac=srcmac, srcname=srcname, app=app, appcat=appcat).inc(1)

            # Rebuild gauges every 30 seconds
            now = time.time()
            if now - last_rebuild >= 30:
                rebuild_gauges()
                last_rebuild = now

        except Exception as e:
            print(f'Error: {e}')
            continue

if __name__ == '__main__':
    main()
