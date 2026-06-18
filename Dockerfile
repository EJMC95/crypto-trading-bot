# Single image shared by all four Railway services.
# Each Railway service overrides the Start Command to run its own bot
# (see RAILWAY_DEPLOY.md). No CMD here on purpose.
FROM python:3.11-slim

WORKDIR /app

# Install deps first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project
COPY . .

ENV PYTHONUNBUFFERED=1

# Default command is a no-op help message; Railway sets the real Start Command
# per service. This prevents an accidental live run if a service has no command.
CMD ["python", "-c", "print('Set this service\\'s Start Command in Railway. See RAILWAY_DEPLOY.md')"]
