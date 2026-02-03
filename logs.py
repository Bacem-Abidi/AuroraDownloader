import os
import json
from datetime import datetime, timedelta
import threading
from queue import Queue, Empty
from pathlib import Path


class LogManager:
    def __init__(self, logs_dir="logs"):
        self.logs_dir = Path(logs_dir)
        self.logs_dir.mkdir(exist_ok=True)
        self.log_queues = {}
        self.active_loggers = {}
        self.save_logs = True  # Default to not saving logs
        self.lock = threading.Lock()

    def set_save_logs(self, enabled):
        """Enable or disable log saving"""
        self.save_logs = enabled

    def start_logging(self, operation_id, operation_type="download"):
        """Start logging for an operation"""
        if not self.save_logs:
            return

        log_queue = Queue()
        self.log_queues[operation_id] = log_queue
        self.active_loggers[operation_id] = {
            "queue": log_queue,
            "type": operation_type,
            "start_time": datetime.now(),
        }

        # Start a thread to write logs to file
        thread = threading.Thread(
            target=self._write_logs_thread,
            args=(operation_id, operation_type),
            daemon=True,
        )
        thread.start()

        return log_queue

    def stop_logging(self, operation_id):
        """Stop logging for an operation"""
        if operation_id in self.active_loggers:
            self.active_loggers[operation_id]["queue"].put("[LOG_END]")
            with self.lock:
                if operation_id in self.log_queues:
                    del self.log_queues[operation_id]
                if operation_id in self.active_loggers:
                    del self.active_loggers[operation_id]

    def log_message(self, operation_id, message):
        """Add a log message to the queue"""
        if operation_id in self.log_queues:
            self.log_queues[operation_id].put(message)

    def _write_logs_thread(self, operation_id, operation_type):
        """Thread function to write logs to file"""
        log_info = self.active_loggers.get(operation_id)
        if not log_info:
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = self.logs_dir / f"{operation_type}_{operation_id}_{timestamp}.log"

        try:
            with open(log_file, "w", encoding="utf-8") as f:
                f.write(f"Operation ID: {operation_id}\n")
                f.write(f"Type: {log_info['type']}\n")
                f.write(f"Start Time: {log_info['start_time'].isoformat()}\n")
                f.write("-" * 80 + "\n\n")

                while True:
                    try:
                        message = log_info["queue"].get(timeout=0.5)
                        if message == "[LOG_END]":
                            f.write(f"\nEnd Time: {datetime.now().isoformat()}\n")
                            break
                        f.write(f"{message}\n")
                        f.flush()
                    except Empty:
                        if operation_id not in self.active_loggers:
                            break
                        continue
        except Exception as e:
            print(f"Error writing log file: {e}")

    def get_log_files(self):
        """Get list of all log files"""
        if not self.logs_dir.exists():
            return []

        log_files = []
        for file in self.logs_dir.glob("*.log"):
            try:
                stats = file.stat()
                log_files.append(
                    {
                        "name": file.name,
                        "size": stats.st_size,
                        "modified": stats.st_mtime,
                        "path": str(file),
                    }
                )
            except:
                continue

        # Sort by modified time (newest first)
        log_files.sort(key=lambda x: x["modified"], reverse=True)
        return log_files

    def get_log_content(self, filename):
        """Get content of a log file"""
        log_file = self.logs_dir / filename
        if not log_file.exists():
            return None

        try:
            with open(log_file, "r", encoding="utf-8") as f:
                return f.read()
        except:
            return None

    def delete_log_file(self, filename):
        """Delete a log file"""
        log_file = self.logs_dir / filename
        if log_file.exists():
            try:
                log_file.unlink()
                return True
            except:
                return False
        return False

    def clear_all_logs(self):
        """Clear all log files"""
        try:
            for file in self.logs_dir.glob("*.log"):
                file.unlink()
            return True
        except:
            return False


# Global log manager instance
log_manager = LogManager()
