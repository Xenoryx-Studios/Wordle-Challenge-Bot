# Use official Python slim image
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Copy project files
COPY . /app

COPY data /app/data

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Environment variable for bot token
ENV DISCORD_TOKEN=""

# Run bot
CMD ["python", "bot.py"]