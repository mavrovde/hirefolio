import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)


# SECURITY (#297 review): httpx logs every request URL at INFO through the
# root handler above — and the Telegram Bot API embeds the BOT TOKEN in the
# URL, so a successful notification printed the credential into the container
# logs (reproduced in the running container). Same for httpcore's debug lines.
# WARNING+ still surfaces real transport problems.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str):
    """Return a logger with the specified name."""
    return logging.getLogger(name)


logger = get_logger("app")
