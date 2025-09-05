# src/logging_config.py
import logging

class TqdmLoggingHandler(logging.Handler):
    def __init__(self, level=logging.NOTSET):
        super().__init__(level)

    def emit(self, record):
        try:
            msg = self.format(record)
            from tqdm import tqdm
            tqdm.write(msg)
            self.flush()
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            self.handleError(record)

def configure_logging():
    logging.root.setLevel(logging.INFO)
    file_handler = logging.FileHandler("console.log")
    file_handler.setLevel(logging.INFO)

    # Create a TqdmLoggingHandler that logs even debug messages
    tqdm_handler = TqdmLoggingHandler()
    tqdm_handler.setLevel(logging.INFO)

    # Define the log format
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
    file_handler.setFormatter(formatter)
    tqdm_handler.setFormatter(formatter)

    # Add handlers to the root logger
    logging.root.addHandler(file_handler)
    logging.root.addHandler(tqdm_handler)

# Ensure configure_logging is called at the start of your application
configure_logging()


