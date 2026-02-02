## dsutil

`dsutil` is a diagnostic utility for **ONLYOFFICE DocumentServer**.

It analyzes the runtime state of DocumentServer and detects common issues in Docker-based and native Linux installations.

---

## Supported platforms

* Docker (Linux) ✅
* Linux (native) ✅
* Windows ✅

---

## Installation (Linux)

```bash
wget https://github.com/nasrullonurullaev/ds-util/releases/download/v1.0.0/dsutil
chmod +x dsutil
```

---

## Usage

⚠️ **Important**

* The utility **must be run with `sudo`**
* The `--platform` option is **mandatory**
* Supported values for `--platform`:

  * `docker`
  * `linux`

### Docker installation

```bash
sudo ./dsutil --platform docker
```

By default, `dsutil` uses the DocumentServer container named:

```text
onlyoffice-documentserver
```

If your container has a different name, specify it explicitly:

```bash
sudo ./dsutil --platform docker --ds <container_name>
```

### Native Linux installation

```bash
sudo ./dsutil --platform linux
```

### Windows installation

Run from an elevated PowerShell prompt:

```powershell
dsutil.exe --platform windows
```

Windows service names checked:

* DsConverterSvc (required)
* DsDocServiceSvc (required)
* DsAdminPanelSvc (optional)
* DsExampleSvc (optional)
* DsProxySvc (optional, nginx)
* RabbitMQ
* postgresql-x64-18
* Redis

---

## Command-line options

| Option                       | Description                                 | Default                     |
| ---------------------------- | ------------------------------------------- | --------------------------- |
| `--platform <docker\|linux>` | Execution platform (**required**)           | —                           |
| `--ds <name>`                | DocumentServer container name (Docker only) | `onlyoffice-documentserver` |
| `--json`                     | Output report in JSON format                | disabled                    |
| `--docker-tail <N>`          | Docker log lines to analyze                 | `400`                       |
| `--file-tail <N>`            | Lines read from each DS log file            | `800`                       |

---

## What is checked

### Container status and healthcheck

### Supervisor services

**Required**

* `ds:docservice`
* `ds:converter`

**Optional**

* `ds:adminpanel`
* `ds:example`
* `ds:metrics`

### Nginx configuration

### Services

* PostgreSQL
* RabbitMQ
* Redis

### DocumentServer logs

* Error patterns
* Timeouts
* OOM events
* Common runtime issues
