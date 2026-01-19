# Standard imports
import logging

# Third Party imports
from colorama import init, Fore, Style

# Color Formatter: Initialize Colorama for cross-platform compatibility and auto-reset
init(autoreset=True)

class ColoredFormatter(logging.Formatter):
    """A custom formatter to add colors based on log level."""
    FORMAT = "[%(levelname)-s] %(message)s"

    LOG_COLORS = {
        logging.DEBUG: Fore.BLUE + Style.DIM,
        logging.INFO: Fore.GREEN,
        logging.WARNING: Fore.YELLOW,
        logging.ERROR: Fore.RED + Style.BRIGHT,
        logging.CRITICAL: Fore.RED + Style.BRIGHT
    }
    RESET = Style.RESET_ALL

    def format(self, record):
        log_color = self.LOG_COLORS.get(record.levelno, self.RESET)
        formatter = logging.Formatter(log_color + self.FORMAT + self.RESET)
        return formatter.format(record)

# Configure the logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Create a stream handler and set the custom formatter
console_handler = logging.StreamHandler()
console_handler.setFormatter(ColoredFormatter())
logger.addHandler(console_handler)
