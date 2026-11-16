# Self-hosting the backend

How to take a clean Ubuntu host on a home LAN to two running environments of the backend, `asc-prod` and
`asc-dev`, each reachable from the internet over HTTPS through its own Tailscale node, and kept up to date by a
timer that pulls new images. The database stays on Neon and the frontend on Cloudflare Workers; only the backend
container runs here.

The pieces in the repository:

| File | What it is |
|---|---|
| [`compose.server.yaml`](../compose.server.yaml) | one environment: the backend and its Tailscale sidecar |
| [`.env.server.example`](../.env.server.example) | the settings of one environment, with placeholders |
| [`ops/server/tailscale-serve.json`](../ops/server/tailscale-serve.json) | the sidecar's HTTPS and Funnel config |
| [`scripts/server-pull.sh`](../scripts/server-pull.sh) | pull, start what changed, prune; one run for all environments |
| [`ops/systemd/`](../ops/systemd/) | `asc-pull.service` and `.timer` (every 5 minutes), `docker-user-lan-block.service` |

How a request reaches the backend: the browser opens `https://asc-prod.<tailnet>.ts.net`, Tailscale Funnel
relays it to the `asc-prod` node, which is the sidecar container; the sidecar terminates TLS and proxies to
`http://backend:8000` over the compose network. No port is open on the router or on the host's LAN address, and
the backend's own port binds to `127.0.0.1` for checks on the host only.

How a new version arrives: the deploy workflow moves the `:dev` or `:prod` tag in ghcr to a new `sha-*` image;
within 5 minutes the timer on the server pulls it and restarts that environment; the workflow waits until
`GET /version` reports the new tag. Nothing from GitHub connects to the server, and there is no self-hosted runner
(the repository is public, and a runner would run code from pull requests on this machine).

Run the steps below on the server, in order. `<tailnet>` stands for your tailnet's DNS name
(`something.ts.net`), and the paths assume the stack user `asc` with its home in `/home/asc`.

## 1. Host

Ubuntu 24.04 LTS, updated: `sudo apt update && sudo apt full-upgrade -y`, then reboot if asked.

### SSH: keys only

From your own machine, copy a key and check that it logs you in: `ssh-copy-id <you>@<server>`. Then, on the
server, keep that session open and turn passwords off:

```bash
sudo tee /etc/ssh/sshd_config.d/10-keys-only.conf >/dev/null <<'EOF'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
EOF
sudo sshd -t && sudo systemctl reload ssh
```

Before closing the open session, check in a new terminal that `ssh <you>@<server>` still logs in, and that
`ssh -o PubkeyAuthentication=no <you>@<server>` is refused with `Permission denied (publickey)`.

### Firewall

Allow SSH from the LAN only, and nothing else in. The stack needs no inbound port: the sidecars connect out to
Tailscale.

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow from 192.168.0.0/16 to any port 22 proto tcp
sudo ufw enable
sudo ufw status verbose
```

Docker publishes ports through its own iptables chains, past ufw. That is why `compose.server.yaml` binds the
backend to `127.0.0.1` only; keep it that way, and for any other project on this host, too.

### Security updates

```bash
sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades   # answer Yes
systemctl status unattended-upgrades --no-pager
```

This covers Ubuntu's security pocket. Docker comes from Docker's own repository below, which unattended-upgrades
does not touch; update it by hand (`sudo apt update && sudo apt upgrade`) and expect the containers to restart.

### Docker

Docker Engine and the Compose plugin from Docker's repository (the steps from
[docs.docker.com](https://docs.docker.com/engine/install/ubuntu/)):

```bash
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" |
  sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
docker compose version
```

Give containers public DNS resolvers. Docker otherwise hands them the host's upstream resolver, which on a home
network is usually the router, and the LAN block in step 2 can then cut them off from DNS:

```bash
sudo tee /etc/docker/daemon.json >/dev/null <<'EOF'
{
  "dns": ["1.1.1.1", "9.9.9.9"]
}
EOF
sudo systemctl restart docker
```

If `/etc/docker/daemon.json` already exists, add the `dns` key to it instead of overwriting the file.

### The stack user

A system user owns the clone, the env files and the timer's runs, so none of it sits in a personal account:

```bash
sudo adduser --system --group --home /home/asc asc
sudo usermod -aG docker asc
```

Membership in the `docker` group is as good as root on this host: the user can start a container that mounts `/`.
What the separate user buys is order (one owner for the stack's files, secrets out of your own home), not a
security boundary. The boundary is in the containers: read-only, all capabilities dropped, no Docker socket.

The clone of this repository (the compose file, the serve config and the pull script come from it):

```bash
sudo -u asc -H git clone https://github.com/vadimvvlasov/anti-scope-creep.git /home/asc/anti-scope-creep
```

`/home/asc` is closed to other users (mode 750), so your own account cannot `cd` into it, and a relative
`-f compose.server.yaml` run as `asc` from your directory points at a file `asc` cannot read. The commands below
therefore use absolute paths. For compose, put this function in your `~/.bashrc`:

```bash
# asc <prod|dev> <compose command...>: compose of one environment, run as the stack user.
asc() {
  (cd / && sudo -u asc docker compose -f /home/asc/anti-scope-creep/compose.server.yaml \
    --env-file "/home/asc/env/$1.env" "${@:2}")
}
```

`asc prod ps`, `asc dev logs --since 1h backend`, `asc prod exec tailscale tailscale status`.

### Env files

One file per environment, readable by `asc` only, outside the clone:

```bash
sudo -u asc install -d -m 700 /home/asc/env
for env in prod dev; do
  sudo -u asc install -m 600 /home/asc/anti-scope-creep/.env.server.example "/home/asc/env/$env.env"
done
sudoedit /home/asc/env/prod.env
sudoedit /home/asc/env/dev.env
sudo ls -l /home/asc/env   # -rw------- asc asc for both
```

What differs between the two files:

| Setting | prod.env | dev.env |
|---|---|---|
| `COMPOSE_PROJECT_NAME` | `asc-prod` | `asc-dev` |
| `IMAGE_TAG` | `prod` | `dev` |
| `PORT` | `8000` | `8001` |
| `DATABASE_URL` | Neon `production` branch, pooled | Neon `dev` branch, pooled |
| `JWT_SECRET` | its own: `openssl rand -base64 48` | its own |
| `CORS_ORIGINS` | the prod frontend origin | the dev frontend origin |
| `ANALYZER` | `groq` (with `GROQ_API_KEY`) | `stub` or `groq` |
| `TS_AUTHKEY` | from step 3 | from step 3 |

`sudoedit` keeps the owner and the mode of the file. Never copy a filled-in file into the clone.

## 2. Block containers from the LAN

A container that is broken into should reach the internet (Neon, Groq, ghcr, Tailscale) and nothing on the home
network: not the router's admin page, not a NAS, not the other machines. Docker passes the host's
`DOCKER-USER` iptables chain before its own forwarding rules and leaves its contents alone, so the block goes
there: reject anything that comes from a Docker bridge (`docker0`, and `br-*` for every compose network of every
project) and goes to `192.168.0.0/16`.

iptables rules do not survive a reboot, so a systemd unit adds them each time Docker starts
([`ops/systemd/docker-user-lan-block.service`](../ops/systemd/docker-user-lan-block.service)). Its commands are
inline in the unit file, which is owned by root, so the stack user cannot change what runs as root.

```bash
sudo install -m 644 /home/asc/anti-scope-creep/ops/systemd/docker-user-lan-block.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now docker-user-lan-block.service
sudo iptables -L DOCKER-USER -v -n
```

The last command lists two `REJECT` rules, `docker0` and `br-+`, both to `192.168.0.0/16`. `WantedBy` and
`PartOf=docker.service` make the unit start with Docker and again when Docker restarts; each rule is added only
if it is not there yet.

Traffic from a container to the host itself does not pass `DOCKER-USER` (it is not forwarded); ufw's
`deny incoming` from step 1 drops it, since containers' addresses (`172.16.0.0/12`) are not in the SSH rule.

The check, from a throwaway container on a compose-style network (the backend image has Python and no curl;
until the `:prod` tag exists, use a `sha-*` tag, see step 4):

```bash
sudo -u asc docker network create lan-check
sudo -u asc docker run --rm --network lan-check --entrypoint python \
  ghcr.io/vadimvvlasov/anti-scope-creep-backend:prod -c '
import socket
def reach(host, port):
    try:
        socket.create_connection((host, port), timeout=3).close()
        return "reachable"
    except OSError as error:
        return f"blocked ({error})"
print("router  ", reach("192.168.0.1", 80))
print("internet", reach("ghcr.io", 443))
'
sudo -u asc docker network rm lan-check
```

Expected: `router blocked (... Connection refused)` and `internet reachable`. Use your router's real address if
it is not `192.168.0.1`. If both are blocked, DNS is the likely cause: check `/etc/docker/daemon.json` from
step 1. After the next reboot, run `sudo iptables -L DOCKER-USER -v -n` and the check again.

This guide assumes Docker's default iptables firewall backend. With the experimental nftables backend
(`"firewall-backend": "nftables"` in `daemon.json`) there is no `DOCKER-USER` chain, and the unit fails at start.

## 3. Tailscale admin

In the [admin console](https://login.tailscale.com/admin), once per tailnet:

1. **DNS:** MagicDNS on; **HTTPS Certificates** on. The node names become `asc-prod.<tailnet>` and
   `asc-dev.<tailnet>`, and Funnel needs the certificates.
2. **Access controls:** edit the policy file. The parts that matter here:

   ```jsonc
   {
     // Who may put tag:asc on a node. Only admins; the auth key below carries it.
     "tagOwners": {
       "tag:asc": ["autogroup:admin"],
     },

     // Funnel (the public HTTPS ingress) for tag:asc only, not for every device.
     "nodeAttrs": [
       {"target": ["tag:asc"], "attr": ["funnel"]},
     ],

     // Your own devices may reach anything, including the asc nodes.
     // tag:asc is not a source in any grant, so its nodes reach no other node of the tailnet.
     "grants": [
       {"src": ["autogroup:member"], "dst": ["*"], "ip": ["*"]},
     ],
   }
   ```

   A new tailnet starts with a grant from `*` to `*`; replace it, because `*` includes tagged nodes. Tagged
   nodes are not members, so `autogroup:member` leaves them out. If the policy uses `acls` instead of `grants`,
   the same rule is `{"action": "accept", "src": ["autogroup:member"], "dst": ["*:*"]}`.
3. **Auth key:** Settings → Keys → Generate auth key: **Reusable** on (one key for both environments),
   **Ephemeral** off (the nodes must outlive a container restart), **Pre-approved** on (if device approval is
   enabled), **Tags** `tag:asc`, **Expiration** 1 day. Put it into `TS_AUTHKEY` of both env files.

   The key is used only for the first login; the node then lives in the sidecar's state volume
   (`asc-prod_tailscale-state`), and tagged nodes have key expiry off. Once both nodes are up, the expired key
   in the env files does no harm, but keep the variable set: `compose.server.yaml` requires it.

The check that a tagged node reaches nothing (after step 5, when the nodes exist). Tailscale sends a node only
the peers it may talk to, in either direction, so `asc-prod` does not even know `asc-dev`:

```bash
asc prod exec tailscale tailscale status            # asc-prod and your own devices; no asc-dev
dev_ip=$(asc dev exec tailscale tailscale ip -4)
asc prod exec tailscale timeout 10 tailscale nc "$dev_ip" 443; echo "rc=$?"
```

Expected: no `asc-dev` in the list, and the `nc` ends with an error or is cut by the timeout (`rc=143`, the
TERM from busybox `timeout`). By name instead of IP, `nc` fails earlier, at the DNS lookup, for the same reason.
In the admin console, Access controls → Preview rules for `tag:asc` shows no destinations. The backend
container cannot reach the tailnet at all: the sidecar runs in userspace mode and does not route the compose
network into the tailnet.

## 4. Pulling from ghcr

The backend image is `ghcr.io/vadimvvlasov/anti-scope-creep-backend`, a public package: no login needed. Check
from the server:

```bash
sudo -u asc docker pull ghcr.io/vadimvvlasov/anti-scope-creep-backend:prod
```

If the package is private (a fork can make it so): create a classic personal access token with
`read:packages` only, and log the stack user in. The token is stored in `/home/asc/.docker/config.json`, mode 600.

```bash
read -rs GHCR_TOKEN   # paste the token, then Enter; it stays out of the shell history
printf '%s' "$GHCR_TOKEN" | sudo -u asc -H docker login ghcr.io -u <github-user> --password-stdin
unset GHCR_TOKEN
```

The sidecar image is also pulled from ghcr (`ghcr.io/tailscale/tailscale`), not from Docker Hub: pulls from Docker
Hub can be slow from a home connection, and one registry is one thing less to reach.

The `:prod` and `:dev` tags exist once the deploy workflows have moved them to an image. Before that, set
`IMAGE_TAG` in the env file to a `sha-*` tag that exists in the package.

## 5. Start both environments

```bash
asc prod up -d --wait
asc dev up -d --wait
sudo -u asc docker ps --format 'table {{.Names}}\t{{.Status}}'
```

Each environment is its own compose project (`asc-prod`, `asc-dev`): its own containers, network, sidecar and
state volume. `--wait` returns once the backend's health check passes. On the server:

```bash
curl -fsS http://127.0.0.1:8000/version   # prod
curl -fsS http://127.0.0.1:8001/version   # dev
asc prod exec tailscale tailscale funnel status
```

`funnel status` shows `https://asc-prod.<tailnet>.ts.net (Funnel on)` proxying to `http://backend:8000`.
From outside the home network (a phone on mobile data, or a machine that is not on the tailnet):

```bash
curl -fsS https://asc-prod.<tailnet>.ts.net/health/ready
curl -fsS https://asc-dev.<tailnet>.ts.net/version
```

In the first minutes after a node appears, Funnel drops some TLS handshakes while its certificate and DNS settle;
retry for a few minutes before you look for a fault. Then point each frontend at its URL (`VITE_API_URL`) and
put the frontend origins into `CORS_ORIGINS`.

### Pull timer

The timer runs [`scripts/server-pull.sh`](../scripts/server-pull.sh) every 5 minutes as `asc`, with both env
files. For each environment it runs `docker compose pull` and `docker compose up -d --wait` (which restarts a
container only if its image changed, and fails if the backend does not become healthy within 3 minutes), then
`docker image prune -f` once for the host (dangling images only, so another project's tagged images stay). A
failing environment does not stop the other, but the run then fails.

```bash
sudo install -m 644 /home/asc/anti-scope-creep/ops/systemd/asc-pull.service \
  /home/asc/anti-scope-creep/ops/systemd/asc-pull.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now asc-pull.timer
sudo systemctl start asc-pull.service      # one run now, to see that it works
systemctl list-timers asc-pull.timer
journalctl -u asc-pull.service -n 30 --no-pager
```

The journal shows one line per environment and run: `prod: up to date`, or `prod: started sha-1a2b3c4` when a
new image came in, or why it failed. `systemctl status asc-pull.service` shows whether the last run failed.

Other paths or another set of environments: `sudo systemctl edit asc-pull.service`, then

```ini
[Service]
ExecStart=
ExecStart=/home/asc/anti-scope-creep/scripts/server-pull.sh /home/asc/env/prod.env
```

The timer pulls images, not the repository. When `compose.server.yaml`, the serve config or the pull script
change on `main`, update the clone by hand and apply it:

```bash
sudo -u asc -H git -C /home/asc/anti-scope-creep pull --ff-only
sudo systemctl start asc-pull.service
```

To stop deploys for a while (an incident, a migration by hand): `sudo systemctl stop asc-pull.timer`, and
`start` it again afterwards.

### Moving an existing setup to the stack user

If the environments already run from another account's clone, copy the env files over unchanged (the same
`JWT_SECRET` keeps users logged in), then move one environment at a time, dev first:

```bash
sudo install -o asc -g asc -m 600 <old-dir>/dev.env /home/asc/env/dev.env
(cd <old-clone> && docker compose -f compose.server.yaml --env-file <old-dir>/dev.env down)   # no -v
asc dev up -d --wait
```

Volumes belong to Docker, not to a user, and the project names are the same, so the sidecar finds its state
volume and comes back as the same Tailscale node, with the same URL. If `up` fails, the same `up -d` from the
old clone brings the environment back. Once both run from `/home/asc`, delete the old env files
(`shred -u`).

## 6. Another project on the same server

Another application gets the same treatment, with nothing shared but the host:

- **Its own compose project** (`name:` in its compose file) and its own env files with `chmod 600`, in its own
  directory (or under its own stack user).
- **Its own sidecar and tag.** A second `tailscale/tailscale` service in its compose file, userspace mode, its own
  serve config proxying to its own service, and its own tag, for example `tag:<other>`. In the policy file, add
  the tag to `tagOwners` and to the `funnel` `nodeAttrs` entry, and keep it out of every grant's `src`. A
  separate auth key with that tag. Each node gets its own Funnel URL on 443, so the projects never compete
  for a port or a Funnel slot.
- **Its own local ports**, bound to `127.0.0.1`, different from `8000` and `8001`.
- **Its own limits.** `mem_limit`, `cpus` and `pids_limit` on every service, so that one project cannot starve the
  other. The asc stack takes at most 2 × (512 MB + 128 MB) of memory and 3 CPUs; size the new project's limits so
  that the sum leaves room for the host. `docker stats --no-stream` shows the real use.
- **The same hardening:** `read_only` with a `tmpfs` where needed, `cap_drop: [ALL]`,
  `no-new-privileges`, no `docker.sock` mount.
- **Its own pull timer**, a copy of `asc-pull.service` and `.timer` under another name and with its own
  compose file (`ASC_COMPOSE_FILE` in an `Environment=` line) and env files.

The LAN block from step 2 already covers it: `br-+` matches every compose network on the host.

## 7. Rollback

Every image stays in ghcr under its `sha-*` tag, so a rollback moves the environment tag back and lets the timer
do the rest. From a machine with write access to the package (`gh auth token` works once
`gh auth refresh -s write:packages` has added that scope; or use a token with it):

```bash
gh auth token | docker login ghcr.io -u <github-user> --password-stdin
docker buildx imagetools create \
  -t ghcr.io/vadimvvlasov/anti-scope-creep-backend:prod \
  ghcr.io/vadimvvlasov/anti-scope-creep-backend:sha-1a2b3c4
```

Within 5 minutes the timer pulls it; `curl -fsS https://asc-prod.<tailnet>.ts.net/version` then reports
`sha-1a2b3c4`. To not wait, run `sudo systemctl start asc-pull.service` on the server. The next deploy moves the
tag forward again.

When the registry cannot be used, pin the environment on the server instead: set `IMAGE_TAG=sha-1a2b3c4` in
`/home/asc/env/prod.env` (`sudoedit`) and run `sudo systemctl start asc-pull.service`. The timer keeps that image
from then on, because the tag no longer moves; set `IMAGE_TAG=prod` again once the fix is out.

Migrations are not rolled back: they run before the new image takes traffic and must stay compatible with the
previous version, so the older image runs on the newer schema
([`deploy.md`](deploy.md), "Promote to prod"; incidents: [`../ops/runbook.md`](../ops/runbook.md)).

## 8. A local LLM on the GPU

An optional third compose project, `llm` ([`compose.llm.yaml`](../compose.llm.yaml)): `llama-server` with
Bonsai 2 27B (`prism-ml/Ternary-Bonsai-2-27B-gguf`, file `Q2_0`, 7.63 GB) on an NVIDIA GPU, with an
OpenAI-compatible API on `127.0.0.1:8080`. The product does not use it yet: the eval decides first
([#114](https://github.com/vadimvvlasov/anti-scope-creep/issues/114)). Written for an RTX 3090 (24 GB).

Why these choices (from the model card and its `KNOWN_ISSUES.md`):

- `Q2_0` runs on the official llama.cpp image; the smaller `PQ2_0` and `PTQ1_0` need PrismML's fork.
- The image is pinned to a build at or after b11556 (older builds load `Q2_0` silently and produce garbage),
  and to CUDA 12: CUDA 13.3 builds segfault on Linux.
- 64K context, one slot, q8_0 KV cache: room for a whole contract and the model's thinking, about 16 GB of VRAM
  in all. Check the real number with `nvidia-smi` after the first request.
- Reasoning effort `medium` from the client: `low` is not supported and `high` returns HTTP 500.

### Sharing the GPU with other projects

The GPU is shared by turns, not split: whoever runs gets nearly all 24 GB. `--sleep-idle-seconds 300` makes
`llama-server` unload the model after 5 idle minutes; the next request loads it again from the volume (seconds,
plus the prompt). Another project on the GPU (for example a PyTorch inference service) must do the same: free
its memory when it is done (`del model; torch.cuda.empty_cache()`, or exit), and not hold it while idle.

Nothing arbitrates between them. If both need the GPU at the same moment, the one that loads second gets an
out-of-memory error. For this project that is a failed analysis the user can retry; the other project must
handle it too. If collisions become common, split the memory instead: a smaller context here (`-c 32768`,
about 12-13 GB in all) and a cap in the other project (`torch.cuda.set_per_process_memory_fraction`).

### The GPU in Docker

The NVIDIA driver must already work on the host (`nvidia-smi`). Then the NVIDIA Container Toolkit
([docs.nvidia.com](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)).
It may already be installed (`nvidia-ctk --version`, `grep -rl libnvidia-container /etc/apt/sources.list.d/`):
then skip the repository lines and run only `nvidia-ctk runtime configure` and the restart. A second list file
for the same repository with another keyring stops `apt update` with "Conflicting values set for option
Signed-By"; delete the newer file.

```bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey |
  sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list |
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' |
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list >/dev/null
sudo apt update && sudo apt install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker   # adds the runtime to /etc/docker/daemon.json, keeps "dns"
cat /etc/docker/daemon.json
sudo systemctl restart docker                        # restarts asc-prod and asc-dev too: a short outage
```

Check that a container sees the GPU:

```bash
sudo -u asc docker run --rm --gpus all ghcr.io/ggml-org/llama.cpp:server-cuda12-b12429 --list-devices
```

Expected: `CUDA0: NVIDIA GeForce RTX 3090 (24... MiB, ... free)`. `(none)` means the toolkit is not in use.

### Start

```bash
cd / && sudo -u asc docker compose -f /home/asc/anti-scope-creep/compose.llm.yaml up -d
sudo -u asc docker logs -f llm-llama-1     # the download, then "server is listening on http://0.0.0.0:8080"
```

The first start downloads the model into the `llm_models` volume (7.63 GB, from Hugging Face; the LAN block
does not affect it). Later starts load it from there in seconds. The pull timer does not touch this project:
the image is pinned, and a new build is a deliberate change in `compose.llm.yaml`.

### Checks

```bash
curl -s http://127.0.0.1:8080/health; echo                 # {"status":"ok"}
curl -s http://127.0.0.1:8080/v1/chat/completions -H 'Content-Type: application/json' -d '{
  "model": "bonsai-2-27b", "reasoning_effort": "medium", "max_tokens": 4000,
  "messages": [{"role": "user", "content": "Name one risk of unlimited revisions in a freelance contract."}]
}' | python3 -c 'import json,sys; r=json.load(sys.stdin); print(r["choices"][0]["message"]["content"]); print(r["usage"], r.get("timings", {}).get("predicted_per_second"))'
nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu --format=csv
```

Expected: a sensible answer, the token usage, the generation speed in tokens per second, and the memory in use
well under 24 GB. Six minutes later, with no requests, `nvidia-smi` should show the memory freed again (the
server is asleep); `docker logs llm-llama-1` says when it went to sleep and woke up.

### The eval from a laptop

The API listens on the server's loopback only. From the laptop, an SSH tunnel makes it `127.0.0.1:8080` there:

```bash
ssh -N -L 8080:127.0.0.1:8080 <you>@<server>     # keep it open in its own terminal
```

Then, in `backend/` on the laptop (the `local` provider needs no key):

```bash
uv run python -m evaluation run --set freelance --run bonsai-q2-medium --provider local \
  --reasoning-effort medium --max-output-tokens 16000
uv run python -m evaluation score --run bonsai-q2-medium --set freelance
```

Results are cached per contract in `eval/runs/<run>/`, so an interrupted run continues where it stopped.
`LOCAL_API_URL`, `LOCAL_MODEL` and `LOCAL_TIMEOUT` (seconds per request, default 900) override the defaults.

### Stop

`cd / && sudo -u asc docker compose -f /home/asc/anti-scope-creep/compose.llm.yaml down` frees the GPU; the
model stays in the volume (`down -v` deletes it).
