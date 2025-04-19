# BigBrotherBot

BigBrotherBot is a Discord bot designed to track and log user activity in voice channels. It integrates with a SQLite-based backend service to store and manage data about voice channel usage, user opt-ins, and session durations.

## Key Features

- **Voice Channel Tracking**: Tracks when users join, leave, or switch voice channels.
- **User Opt-In System**: Allows users to opt in to the tracking system via a Discord command.
- **Database Integration**: Logs voice channel activity and user data into a SQLite database via a REST API.
- **Retry Mechanism**: Automatically retries failed database calls to ensure data consistency.
- **Kubernetes-Ready**: Designed to run in a Kubernetes environment with environment variables for configuration.

## How It Works

1. **Voice Channel Events**:
   - Tracks when users join, leave, or switch voice channels.
   - Logs session start and end times for each voice channel.

2. **User Opt-In**:
   - Users can opt in to the tracking system using the `/opt_in` command.
   - Opted-in users' data is stored in the database.

3. **Database Operations**:
   - Uses a REST API to interact with a SQLite database service.
   - Automatically creates necessary tables if they do not exist.

4. **Retry Mechanism**:
   - Failed database calls are queued and retried periodically.

## Commands

- `/opt_in`: Opt in to the voice channel tracking system.

## Setup Instructions

1. **Environment Variables**:
   - `DISCORD_BOT_TOKEN`: Your Discord bot token.
   - `SQLITE_SERVICE_URL`: URL of the SQLite service (default: `http://sqlite-service:8080`).

2. **Run the Bot**:
   - Install dependencies:
     ```bash
     pip install -r requirements.txt
     ```
   - Start the bot:
     ```bash
     python main.py
     ```

3. **Deploy to Kubernetes**:
   - Use the provided Kubernetes deployment template to deploy the bot and SQLite service.

## Requirements

- Python 3.8+
- Discord.py library
- SQLite backend service with a REST API

## Future Enhancements

- Add more commands for user management and reporting.
- Improve error handling and logging.

BigBrotherBot simplifies voice channel tracking and provides a robust system for managing user activity data in Discord servers.