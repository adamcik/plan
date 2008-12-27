import logging

DATE_TIME_FORMAT = '%Y-%m-%d %H:%M:%S'
CONSOLE_LOG_FORMAT = '[%(asctime)s %(levelname)s] %(message)s'

def init_console(level=logging.DEBUG):
    logging.basicConfig(
        format=CONSOLE_LOG_FORMAT,
        datefmt=DATE_TIME_FORMAT,
        level=level
    )
