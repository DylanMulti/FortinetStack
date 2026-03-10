# FortiGate 40F Monitoring Stack

A self-hosted network monitoring stack for FortiGate firewalls using open-source tools.
Provides real-time visibility into firewall health, per-device bandwidth usage, and application-level traffic breakdown.

## Stack Components

| Container | Image | Purpose |
|---|---|---|
| grafana | grafana/grafana:latest | Dashboards and visualisation |
| loki | grafana/loki:3.0.0 | Log storage and querying |
| alloy | grafana/alloy:latest | Tails fortigate.log and ships to Loki |
| prometheus | prom/prometheus:v2.51.2 | Metrics storage (90 day retention) |
| snmp-exporter | prom/snmp-exporter:latest | Polls FortiGate via SNMP |
| logparser | custom Python | Per-device bandwidth metrics from syslog |

## Architecture
```
FortiGate 40F → rsyslog :514 → /var/log/fortigate.log → Alloy → Loki → Grafana
FortiGate 40F → SNMP :161 → SNMP Exporter :9116 → Prometheus → Grafana
FortiGate 40F → rsyslog → logparser :9200 → Prometheus → Grafana
```

## Dashboards

- **Firewall Overview** — CPU, memory, active sessions, session rate, WAN/LAN throughput, interface status
- **Staff Usage Overview** — Per-device download/upload, top apps, app category breakdown, social media and streaming timelines
- **Device Drill Down** — Per-device selector, app usage table, category pie chart, social/streaming detail

## Requirements

- Ubuntu 24.04 LTS VM (2+ vCPU, 4GB+ RAM, 40GB+ disk)
- Docker Engine 24+ with Compose v2
- FortiGate firewall with syslog and SNMP enabled

## Quick Start
```bash
# Clone the repo
git clone https://github.com/DylanMulti/FortinetStack.git
cd FortinetStack

# Set up rsyslog to receive FortiGate syslog
sudo touch /var/log/fortigate.log
sudo chown syslog:adm /var/log/fortigate.log
sudo chmod 640 /var/log/fortigate.log

sudo tee /etc/rsyslog.d/fortigate.conf > /dev/null << 'EOF'
module(load="imudp")
input(type="imudp" port="514")
*.* action(type="omfile" file="/var/log/fortigate.log")
EOF

sudo systemctl restart rsyslog

# Start the stack
docker compose up -d
```

## FortiGate Configuration

**Syslog** — run in FortiGate CLI:
```
config log syslogd setting
    set status enable
    set server "<VM-IP>"
    set facility user
end
```

**SNMP** — run in FortiGate CLI:
```
config system snmp sysinfo
    set status enable
end
config system snmp community
    edit 1
    set name "public"
    config hosts
        edit 1
        set ip <VM-IP> 255.255.255.255
        next
    end
    next
end
```

## Autostart

A systemd service is used to start the stack automatically on boot:
```bash
sudo nano /etc/systemd/system/monitoring.service
```
```ini
[Unit]
Description=FortiGate Monitoring Stack
Requires=docker.service
After=docker.service network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/home/dylanmulti/monitoring
ExecStart=/usr/bin/docker compose up -d --remove-orphans
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=300
User=dylanmulti
Group=dylanmulti

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl daemon-reload
sudo systemctl enable monitoring.service
```

## Grafana Access

- URL: `http://<VM-IP>:3000`
- Default credentials: `admin / changeme123` — **change on first login**

## Documentation

- `FortiGate_Capabilities_Overview.docx` — What is monitored, limitations, upgrade path
- `FortiGate_Stack_Setup_Guide.docx` — Full deployment guide

---

*Built and maintained by [Multi IT — Integrated ICT Solutions](https://www.multiit.co.za)* 
