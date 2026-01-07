# -------------------------------------------------------------------------------- #
# ELSR Makefile
# -------------------------------------------------------------------------------- #


# -------------------------------------------------------------------------------- #
# Colours
# -------------------------------------------------------------------------------- #

Clear   := \033[0m
Red     := \033[0;31m
Green   := \033[0;32m
Yellow  := \033[1;33m
Blue    := \033[0;34m
Magenta := \033[0;35m
Cyan    := \033[0;36m
White   := \033[1;37m


# -------------------------------------------------------------------------------- #
# Help
# -------------------------------------------------------------------------------- #

.DEFAULT_GOAL := help

help:
	@printf "\n"
	@printf "  ${Magenta}ELSR Docker build & run${Clear}\n"
	@printf "\n"
	@printf "  Helper commands for building and running the ELSR website both locally\n"
	@printf "  on macOS (ARM64) and also for remote GCP deployments (x86) using Docker Compose.\n"
	@printf "\n"
	@printf "  Both builds use the local source tree, named Docker volumes etc.\n"
	@printf "  When run locally, the ${Cyan}run_docker.env${Clear} file is used for local configuration.\n"
	@printf "\n"
	@printf "  Remote (GCP) deployments have their own ${Cyan}docker-compose.yaml${Clear} and ${Cyan}env${Clear} files.\n"
	@printf "\n"
	@printf "  Local Usage:\n"
	@printf "    ${Cyan}make local-build${Clear}            - build the local Flask image\n"
	@printf "    ${Cyan}make local-up${Clear}               - start all containers locally\n"
	@printf "    ${Cyan}make local-down${Clear}             - stop all containers\n"
	@printf "    ${Cyan}make local-restart${Clear}          - restart containers without building\n"
	@printf "    ${Cyan}make local-logs${Clear}             - show logs for current deployment\n"
	@printf "    ${Cyan}make local-rebuild-nginx${Clear}    - rebuild Nginx eg after docker-compose change\n"
	@printf "    ${Cyan}make local-rebuild-postgres${Clear} - rebuild Postgres eg after docker-compose change\n"
	@printf "\n"
	@printf "  Common workflows:\n"
	@printf "    ${Magenta}Edit code → rebuild → start${Clear}\n"
	@printf "    ${Cyan}make local-build${Clear}\n"
	@printf "    ${Cyan}make local-up${Clear}\n"
	@printf "    ${Cyan}make local-logs${Clear}\n"
	@printf "\n"
	@printf "    ${Magenta}Restart without rebuilding${Clear}\n"
	@printf "    ${Cyan}make local-restart${Clear}\n"
	@printf "\n"
	@printf "  Remote Usage:\n"
	@printf "    ${Cyan}make remote-build${Clear}            - build ARM64 image, save and scp to GCP\n"
	@printf "    ${Cyan}make remote-deploy-web${Clear}	 - deploy elsr-web on GCP\n"
	@printf "    ${Cyan}make remote-ps${Clear}               - container status on GCP\n"
	@printf "    ${Cyan}make remote-logs${Clear}             - logs from GCP\n"
	@printf "    ${Cyan}make remote-restart${Clear}          - restart all containers on GCP\n"
	@printf "    ${Cyan}make remote-rebuild-nginx${Clear}    - rebuild Nginx eg after docker-compose change on GCP\n"
	@printf "    ${Cyan}make remote-rebuild-postgres${Clear} - rebuild Postgres eg after docker-compose change on GCP\n"
	@printf "\n"	
	@printf "  Common workflows:\n"
	@printf "    ${Magenta}Edit code → rebuild → push to GCP → restart${Clear}\n"
	@printf "    ${Cyan}make remote-build${Clear}\n"
	@printf "    ${Cyan}make remote-deploy-web${Clear}\n"
	@printf "    ${Cyan}make remote-logs${Clear}\n"
	@printf "\n"
	@printf "  Notes:\n"
	@printf "    • Local builds target ${Yellow}ARM64${Clear} (Apple Silicon)\n"
	@printf "    • Remote builds target ${Yellow}AMD64${Clear} (x86 etc)\n"
	@printf "    • Static, uploads, and config are stored in Docker volumes\n"
	@printf "    • Database data persists unless volumes are removed\n"
	@printf "\n"


# -------------------------------------------------------------------------------- #
# Local (ARM64 – MBP)
# -------------------------------------------------------------------------------- #

local-build:
	docker compose build

local-up:
	docker compose up -d
	@printf "→ ${Cyan}Local: Getting container status${Clear}\n"
	docker compose ps

local-down:
	docker compose down

local-rebuild-postgres:
	docker compose up -d --force-recreate postgres
	@printf "→ ${Cyan}Local: Getting container status${Clear}\n"
	docker compose ps

local-rebuild-nginx:
	docker compose up -d --force-recreate nginx
	@printf "→ ${Cyan}Local: Getting container status${Clear}\n"
	docker compose ps

local-restart:
	docker compose restart
	@printf "→ ${Cyan}Local: Getting container status${Clear}\n"
	docker compose ps

local-logs:
	docker compose logs -f


# -------------------------------------------------------------------------------- #
# Remote (AMD64 – GCP)
# -------------------------------------------------------------------------------- #

remote-build:
	@printf "1. ${Magenta}Building elsr-web for AMD64${Clear}...\n"
	docker buildx build \
		--platform linux/amd64 \
		-t elsr-web:latest \
		.
	@printf "2. ${Magenta}Saving image${Clear}\n"
	docker save elsr-web:latest | gzip > elsr-web-amd64.tar.gz
	@printf "3. ${Magenta}Pushing file to GCP (elsr2)${Clear}...\n"
	scp elsr-web-amd64.tar.gz elsr2:/home/deploy/elsr/
	@printf "4. ${Magenta}Remember to sync any new static resources etc!${Clear}\n"

remote-deploy-web:
	@printf "\n${Magenta}Deploying elsr-web to GCP${Clear}\n"
	@printf "→ ${Cyan}Loading Docker image${Clear}\n"
	ssh elsr2 "cd /home/deploy/elsr && docker load < elsr-web-amd64.tar.gz"
	@printf "→ ${Cyan}Recreating elsr-web container${Clear}\n"
	ssh elsr2 "cd /home/deploy/elsr && docker compose up -d --force-recreate elsr"
	@printf "→ ${Cyan}GCP: Getting container status${Clear}\n"
	ssh elsr2 "cd /home/deploy/elsr && docker compose ps"
	@printf "\n"

remote-ps:
	@printf "→ ${Cyan}GCP: Getting container status${Clear}\n"
	ssh elsr2 "cd /home/deploy/elsr && docker compose ps"
	@printf "\n"

remote-logs:
	@printf "\n${Magenta}GCP Website Logs${Clear}\n"
	ssh elsr2 "cd /home/deploy/elsr && docker compose logs -f"

remote-restart:
	@printf "\n${Magenta}GCP UP${Clear}\n"
	ssh elsr2 "cd /home/deploy/elsr && docker compose restart"
	@printf "→ ${Cyan}GCP: Getting container status${Clear}\n"
	ssh elsr2 "cd /home/deploy/elsr && docker compose ps" 
	@printf "\n"

remote-rebuild-postgres:
	@printf "\n${Magenta}GCP postgres rebuild${Clear}\n"
	ssh elsr2 "cd /home/deploy/elsr && docker compose up -d --force-recreate postgres"
	@printf "→ ${Cyan}GCP: Getting container status${Clear}\n"
	ssh elsr2 "cd /home/deploy/elsr && docker compose ps"
	@printf "\n"

remote-rebuild-nginx:
	@printf "\n${Magenta}GCP nginx rebuild${Clear}\n"
	ssh elsr2 "cd /home/deploy/elsr &&docker compose up -d --force-recreate nginx"
	@printf "→ ${Cyan}GCP: Getting container status${Clear}\n"
	ssh elsr2 "cd /home/deploy/elsr && docker compose ps"
	@printf "\n"


