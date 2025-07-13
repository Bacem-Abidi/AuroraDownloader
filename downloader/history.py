from history import HistoryLogger

class HistoryManager:
    def __init__(self, history_dir):
        self.logger = HistoryLogger(history_dir)
    
    def log_download(self, entry):
        self.logger.log_download(entry)
