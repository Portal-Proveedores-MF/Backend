import logging
import json
import sys

class JsonFormatter(logging.Formatter):
    def format(self, record):
        base = {
            "severity": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }
        if record.args and isinstance(record.args, dict):
            base.update(record.args)
        return json.dumps(base)

def setup_logging():
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler])

