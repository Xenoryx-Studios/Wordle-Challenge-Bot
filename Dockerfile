# Use official Python slim image
FROM python:3.14-slim

# Set working directory
WORKDIR /app

# Copy project files
COPY . /app

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Run as a non-root user
RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app
USER appuser

# DISCORD_TOKEN must be supplied at runtime (e.g. `docker run -e DISCORD_TOKEN=...`)

# Run bot
CMD ["python", "bot.py"]