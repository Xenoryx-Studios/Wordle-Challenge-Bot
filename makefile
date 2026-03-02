# Project variables
IMAGE_NAME = wordle-bot
CONTAINER_NAME = wordle-bot
TOKEN =

# Build Docker image
build:
	docker build -t $(IMAGE_NAME) .

# Run Docker container
run:
	docker run -d --name $(CONTAINER_NAME) \
	-e DISCORD_TOKEN=$(TOKEN) \
	-v $(PWD)/data:/app/data \
	-v $(PWD)/guild_config.json:/app/guild_config.json \
	$(IMAGE_NAME)

# Stop and remove container
stop:
	docker rm -f $(CONTAINER_NAME)

# Rebuild and run
rebuild: stop build run

# Tail logs
logs:
	docker logs -f $(CONTAINER_NAME)