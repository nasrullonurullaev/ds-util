# dsutil

`dsutil` is a diagnostic utility for **ONLYOFFICE DocumentServer**.

It analyzes the runtime state of DocumentServer and detects common issues in
Docker-based installations.

---

## Supported platforms

* Docker (Linux) ✅
* Linux (native) ⏳
* Windows ⏳

---

## Installation (Linux)

```bash
wget https://github.com/nasrullonurullaev/ds-util/releases/download/v0.3.0/dsutil
chmod +x dsutil
./dsutil
```

---

## Command-line options

| Option              | Description                      | Default                     |
| ------------------- | -------------------------------- | --------------------------- |
| `--ds <name>`       | DocumentServer container name    | `onlyoffice-documentserver` |
| `--json`            | Output report in JSON format     | disabled                    |
| `--docker-tail <N>` | Docker log lines to analyze      | `400`                       |
| `--file-tail <N>`   | Lines read from each DS log file | `800`                       |
| `--platform`        | Execution platform               | `docker`                    |

---

## What is checked

* Container status and healthcheck
* Supervisor services:

  * Required: `ds:docservice`, `ds:converter`
  * Optional: `ds:adminpanel`, `ds:example`, `ds:metrics`
* Nginx configuration
* PostgreSQL, RabbitMQ, Redis
* DocumentServer logs (error patterns, timeouts, OOM, etc.)

---
