# Remote Access: Local Ollama to Remote Nextcloud

## Configuration

- **Local Machine (LM):** Current machine (christoph)
- **Remote Server (RS):** 78.47.232.138 (alias: `cps1`)
- **SSH Key:** `~/.ssh/vcomtec/chrsch_id_rsa`
- **Ollama API Port (Local):** 11434
- **Tunnel Port (Remote):** 11435

## Architecture

```
┌─────────────────────────────┐         ┌─────────────────────────────┐
│  Local Machine (LM)         │         │  Remote Server (RS)         │
│                             │         │  78.47.232.138              │
│  ┌───────────────────────┐  │         │                             │
│  │ Ollama Container (OC) │  │         │  ┌───────────────────────┐  │
│  │ API: localhost:11434  │◄─┼─────────┼──┤ Nextcloud Container   │  │
│  └───────────────────────┘  │ Reverse │  │ (NC)                  │  │
│                             │ Tunnel  │  └───────────────────────┘  │
└─────────────────────────────┘         └─────────────────────────────┘
```

## Solution: SSH Reverse Tunnel

The local machine creates an SSH reverse tunnel to the remote server, making the Ollama API (localhost:11434) available to the Nextcloud container on the remote server.

**How it works:**
- `-R 11435:localhost:11434` - Forward remote port 11435 to local port 11434 (where Ollama runs)
- `-N` - Don't execute remote commands (tunnel only)
- `-f` - Run in background (optional)

---

## Step-by-Step Setup

### Step 1: Verify Local Ollama is Running

Test that Ollama is accessible on your local machine:

```bash
curl http://localhost:11434/api/version
```

**Expected output:** JSON response with version information

**If it fails:**
- Check if Ollama is running: `docker ps | grep ollama`
- Start Ollama if needed: `docker start ollama` (or however you run it)

---

### Step 2: Test SSH Connection

Verify you can connect to the remote server:

```bash
cps1
```

Type `exit` to return to your local machine.

---

### Step 3: Create the Reverse Tunnel (Test Mode)

Create a temporary reverse tunnel to test:

```bash
ssh -i ~/.ssh/vcomtec/chrsch_id_rsa -R 11435:localhost:11434 root@78.47.232.138 -N
```

**Leave this terminal running** (no `-f` flag for testing) and open a new terminal for the next step.

---

### Step 4: Verify the Tunnel Works

In a **new terminal**, SSH into the remote server:

```bash
cps1
```

Then test the tunneled connection:

```bash
curl http://localhost:11435/api/version
```

**Expected result:** Same JSON response you got in Step 1 ✓

**If it works:** The tunnel is functioning! Exit this SSH session.

---

### Step 5: Configure Docker to Access the Tunnel

On the remote server, edit your Nextcloud docker-compose file (likely `docker-compose.yml` or `docker-compose.override.yml`):

```yaml
services:
  nextcloud:
    extra_hosts:
      - "ollama:host-gateway"
    # ... rest of your config
```

**What this does:** Maps the hostname `ollama` to the Docker host IP, allowing the container to reach `localhost:11435` on the host machine.

Then restart Nextcloud:

```bash
docker-compose restart nextcloud
# Or: docker compose restart nextcloud (depending on your Docker Compose version)
```

---

### Step 6: Test from Nextcloud Container

Verify the Nextcloud container can reach Ollama:

```bash
# Find your Nextcloud container name
docker ps | grep nextcloud

# Test connection (replace <container-name> with actual name)
docker exec -it <container-name> curl http://ollama:11435/api/version
```

**Success:** You should see the Ollama version JSON ✓

---

### Step 7: Configure Nextcloud to Use Ollama

In Nextcloud's admin settings (AI/Ollama settings), set the API endpoint to:

```
http://ollama:11435
```

Test the connection from within Nextcloud's admin interface.

---

### Step 8: Stop the Test Tunnel

Go back to the terminal where the tunnel is running (Step 3) and press `Ctrl+C` to stop it.

**Now proceed to make it permanent** using the automation section below.

---

## Make It Permanent: Automation

### Option A: Using AutoSSH with Systemd (Recommended)

AutoSSH automatically restarts the tunnel if it drops, and systemd ensures it starts on boot.

**1. Install autossh:**

```bash
sudo apt-get update
sudo apt-get install autossh
```

**2. Create a systemd service:**

```bash
sudo nano /etc/systemd/system/ollama-tunnel.service
```

**3. Add this configuration:**

```ini
[Unit]
Description=SSH Reverse Tunnel for Ollama API
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=christoph
Environment="AUTOSSH_GATETIME=0"
ExecStart=/usr/bin/autossh -M 0 -N -R 11435:localhost:11434 root@78.47.232.138 \
  -i /home/christoph/.ssh/vcomtec/chrsch_id_rsa \
  -o "ServerAliveInterval=30" \
  -o "ServerAliveCountMax=3" \
  -o "StrictHostKeyChecking=no" \
  -o "ExitOnForwardFailure=yes"
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**4. Enable and start the service:**

```bash
sudo systemctl daemon-reload
sudo systemctl enable ollama-tunnel
sudo systemctl start ollama-tunnel
```

**5. Check the status:**

```bash
sudo systemctl status ollama-tunnel
```

You should see "active (running)" in green.

**6. View logs if needed:**

```bash
sudo journalctl -u ollama-tunnel -f
```

---

### Option B: Simple Background Tunnel

If you don't want to set up a systemd service, you can run the tunnel in the background:

```bash
ssh -i ~/.ssh/vcomtec/chrsch_id_rsa -R 11435:localhost:11434 root@78.47.232.138 -N -f
```

The `-f` flag runs it in the background.

**To stop it later:**

```bash
# Find the process
ps aux | grep "11435:localhost:11434"

# Kill it (replace <PID> with the process ID)
kill <PID>
```

**Limitations:**
- Won't restart if disconnected
- Won't start automatically after reboot
- Less robust than AutoSSH

---

### Option C: Create a Convenient Alias

Add to your `~/.bashrc` or `~/.bash_aliases`:

```bash
alias ollama-tunnel='ssh -i ~/.ssh/vcomtec/chrsch_id_rsa -R 11435:localhost:11434 root@78.47.232.138 -N'
alias ollama-tunnel-bg='ssh -i ~/.ssh/vcomtec/chrsch_id_rsa -R 11435:localhost:11434 root@78.47.232.138 -N -f'
```

Then reload:

```bash
source ~/.bashrc
```

Now you can simply run:

```bash
ollama-tunnel       # Foreground (Ctrl+C to stop)
# or
ollama-tunnel-bg    # Background
```

---

## Troubleshooting

### Issue: "Connection refused" from remote server

**Diagnosis:**
1. Is Ollama running locally? `curl http://localhost:11434/api/version`
2. Is the tunnel still active? `ps aux | grep 11435`

**Solution:** Restart the tunnel

---

### Issue: Nextcloud container can't reach Ollama

**Diagnosis:**
1. Is `extra_hosts` properly configured in docker-compose.yml?
2. Did you restart the Nextcloud container after editing docker-compose.yml?
3. Test from inside the container: `docker exec -it <container> curl http://ollama:11435/api/version`

**Common fixes:**
- Verify docker-compose.yml syntax
- Try `docker compose down && docker compose up -d` for a full restart
- Check if the hostname `ollama` resolves: `docker exec -it <container> ping ollama`

---

### Issue: Tunnel keeps disconnecting

**Solution:** Use AutoSSH with systemd (Option A above) - it automatically reconnects.

---

### Issue: Port already in use on remote server

**Diagnosis:**

```bash
# On remote server (SSH into cps1)
sudo netstat -tlnp | grep 11435
# or
sudo ss -tlnp | grep 11435
```

**Solution:** Kill the existing process or use a different port.

---

### Issue: "Permission denied" or systemd service fails

**Check:**
1. SSH key permissions: `ls -la ~/.ssh/vcomtec/chrsch_id_rsa` (should be 600)
2. If needed: `chmod 600 ~/.ssh/vcomtec/chrsch_id_rsa`

**Check service logs:**

```bash
sudo journalctl -u ollama-tunnel -n 50 --no-pager
```

**Common issues:**
- Wrong file paths in service file
- Incorrect username in service file
- SSH key not readable by the user

---

## Security Considerations

### 1. Localhost binding (secure by default)
By default, `-R 11435:localhost:11434` only exposes the port on `localhost` of the remote server, NOT to the external network. This is secure.

### 2. Docker container access
The Nextcloud container accesses it via the Docker host, which is the intended behavior.

### 3. No external exposure
The Ollama API is NOT exposed to the internet - only accessible by:
- Your local machine
- The remote server's localhost
- Docker containers on the remote server (via host-gateway)

### 4. SSH key permissions
Ensure your SSH key has proper permissions:

```bash
chmod 600 ~/.ssh/vcomtec/chrsch_id_rsa
```

---

## Testing Checklist

- [ ] Local Ollama API responds: `curl http://localhost:11434/api/version` ✓
- [ ] SSH tunnel establishes without errors ✓
- [ ] Remote server can access: `ssh root@78.47.232.138 "curl http://localhost:11435/api/version"` ✓
- [ ] Docker container can reach it: `docker exec <container> curl http://ollama:11435/api/version` ✓
- [ ] Nextcloud admin panel shows successful Ollama connection ✓
- [ ] Tunnel persists (if using AutoSSH) ✓
- [ ] Tunnel auto-restarts after disconnection (if using AutoSSH) ✓
- [ ] Tunnel starts on reboot (if using systemd) ✓

---

## Quick Reference Commands

### Manual tunnel (foreground):
```bash
ssh -i ~/.ssh/vcomtec/chrsch_id_rsa -R 11435:localhost:11434 root@78.47.232.138 -N
```

### Manual tunnel (background):
```bash
ssh -i ~/.ssh/vcomtec/chrsch_id_rsa -R 11435:localhost:11434 root@78.47.232.138 -N -f
```

### AutoSSH (manual start):
```bash
autossh -M 0 -N -R 11435:localhost:11434 root@78.47.232.138 \
  -i ~/.ssh/vcomtec/chrsch_id_rsa \
  -o "ServerAliveInterval 30" -o "ServerAliveCountMax 3"
```

### Systemd service commands:
```bash
sudo systemctl start ollama-tunnel    # Start
sudo systemctl stop ollama-tunnel     # Stop
sudo systemctl status ollama-tunnel   # Check status
sudo systemctl restart ollama-tunnel  # Restart
sudo journalctl -u ollama-tunnel -f   # View logs
```

### Check if tunnel is running:
```bash
ps aux | grep "11435:localhost:11434"
```

### Test from remote server:
```bash
ssh root@78.47.232.138 "curl http://localhost:11435/api/version"
```

### Kill manual tunnel:
```bash
pkill -f "11435:localhost:11434"
```
