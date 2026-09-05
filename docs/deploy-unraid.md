# Put HomeStock on Unraid

Every command below runs in the Unraid terminal, as root. The application and
the database each run in their own container on a private Docker network. The
web interface answers on port 7850.

The image is built on the server from the GitHub repository, so no registry
account is necessary.

## 1. Make the directories

```bash
mkdir -p /mnt/user/appdata/homestock/{db,uploads,backups,config}
```

## 2. Make the private network

```bash
docker network create homestock
```

The command answers "network already exists" on a second run. That is safe.

## 3. Start PostgreSQL 16

Choose a database password and keep it. The application needs the same one.

```bash
DB_PASSWORD='change-this-password'

docker run -d \
  --name homestock-db \
  --network homestock \
  --restart unless-stopped \
  -e POSTGRES_USER=homestock \
  -e POSTGRES_PASSWORD="$DB_PASSWORD" \
  -e POSTGRES_DB=homestock \
  -e PGDATA=/var/lib/postgresql/data/pgdata \
  -v /mnt/user/appdata/homestock/db:/var/lib/postgresql/data \
  postgres:16-alpine
```

`PGDATA` names a subdirectory. PostgreSQL refuses to start when its data
directory is the mount point itself and the share holds anything else.

## 4. Build the application image

Unraid holds no `git` command, and the Docker daemon needs one to read a git
address. So download the code first, then build from the directory:

```bash
mkdir -p /tmp/homestock-src && cd /tmp/homestock-src
curl -fsSL https://github.com/skermiebroTech/Home-Inventory/archive/refs/heads/main.tar.gz \
  | tar xz --strip-components=1
docker build -t homestock:latest -f docker/Dockerfile .
```

The build takes a few minutes. It compiles the web interface and installs the
Python packages.

On a computer that does hold `git`, one command does the same job:

```bash
docker build -t homestock:latest -f docker/Dockerfile \
  https://github.com/skermiebroTech/Home-Inventory.git#main
```

## 5. Start the application

```bash
SECRET_KEY=$(openssl rand -hex 32)
echo "$SECRET_KEY" > /mnt/user/appdata/homestock/config/secret-key.txt

docker run -d \
  --name homestock \
  --network homestock \
  --restart unless-stopped \
  -p 7850:7850 \
  -e PUID=99 \
  -e PGID=100 \
  -e TZ=Australia/Brisbane \
  -e HS_SECRET_KEY="$SECRET_KEY" \
  -e HS_DATABASE_URL="postgresql+asyncpg://homestock:$DB_PASSWORD@homestock-db:5432/homestock" \
  -e HS_CORS_ORIGINS='*' \
  -e HS_AI_ENABLED=false \
  -v /mnt/user/appdata/homestock/uploads:/data/uploads \
  -v /mnt/user/appdata/homestock/backups:/data/backups \
  -v /mnt/user/appdata/homestock/config:/data/config \
  homestock:latest
```

Keep the secret key. Every access token stops working when it changes, and
everybody must sign in again.

The container runs the database migrations on start, before the server
listens.

## 6. Check it

```bash
docker logs -f homestock          # Ctrl-C leaves the log
curl -fsS http://localhost:7850/api/health
```

A healthy reply reads `"status":"ok"`. The status is `degraded` when Ollama is
away, and the inventory still works.

Now open `http://TOWER-IP:7850` in a browser and make the first account. That
account owns the installation and becomes the administrator.

## 7. The phone

The phone asks for a server address on the sign-in screen. Give it
`http://TOWER-IP:7850`. The phone must be on the same network, or reach the
server through your own VPN.

## 8. The AI, if you want it

The AI is optional, and every model runs on the CPU. If an Ollama container
already runs on the server, put it on the same network and point the
application at it:

```bash
docker network connect homestock ollama
docker rm -f homestock     # then run the command in step 5 again, with:
                           #   -e HS_AI_ENABLED=true
                           #   -e HS_OLLAMA_URL=http://ollama:11434
docker exec ollama ollama pull moondream      # the vision model
docker exec ollama ollama pull llama3.2:3b    # the text model for receipts
```

A small vision model needs five to twenty seconds for one image on a CPU. A
7B model needs one to two minutes, which is too slow.

## 9. A new version

```bash
cd /tmp/homestock-src && rm -rf ./* && \
  curl -fsSL https://github.com/skermiebroTech/Home-Inventory/archive/refs/heads/main.tar.gz \
  | tar xz --strip-components=1
docker build -t homestock:latest -f docker/Dockerfile .
docker rm -f homestock
# run the command in step 5 again, with the same secret key:
SECRET_KEY=$(cat /mnt/user/appdata/homestock/config/secret-key.txt)
```

The migrations run again on start. They only add what is missing.

## The template, if you prefer the Docker tab

Unraid reads user templates from the flash drive. This command writes the
template and points it at the image that step 4 builds:

```bash
curl -fsSL https://raw.githubusercontent.com/skermiebroTech/Home-Inventory/main/unraid/home-inventory.xml \
  | sed 's|ghcr.io/skermiebrotech/home-inventory:latest|homestock:latest|' \
  > /boot/config/plugins/dockerMan/templates-user/my-HomeInventory.xml
```

The name must start with `my-`, or the Docker tab does not list it.

To copy the file from your computer instead:

```bash
scp unraid/home-inventory.xml \
  root@TOWER:/boot/config/plugins/dockerMan/templates-user/my-HomeInventory.xml
```

Then open the **Docker** tab, choose **Add Container**, and pick
**HomeInventory** under the user templates. Fill in the secret key and the
database address, and the fields carry the rest.

The template holds no database path, because PostgreSQL runs in its own
container. Step 3 starts that one.

## 10. Backups

The application writes a backup into
`/mnt/user/appdata/homestock/backups`. The Settings page in the web interface
sets the time and how many to keep. The archive holds the database and the
photographs, and the same page reads one back.

Add that directory to your Unraid backup share, or to the CA Backup plugin.
