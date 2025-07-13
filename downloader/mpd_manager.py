import subprocess

class MPDManager:
    def update_mpd(self, mpd_options, log_queue):
        """Update MPD library using mpc command"""
        try:
            mpc_path = mpd_options.get('mpc_path', 'mpc')
            mpc_command = mpd_options.get('mpc_command', 'update')
            
            log_queue.put(f"[MPD] Updating library with command: {mpc_path} {mpc_command}")
            
            # Run the command
            result = subprocess.run(
                [mpc_path, mpc_command],
                capture_output=True,
                text=True,
                timeout=30  # Prevent hanging
            )
            
            if result.returncode == 0:
                log_queue.put(f"[MPD] Output: {result.stdout.strip()}")
                log_queue.put(f"[MPD] Library updated successfully")
            else:
                log_queue.put(f"[ERROR] MPD update failed with code {result.returncode}")
                log_queue.put(f"[MPD] Error: {result.stderr.strip()}")
                
        except FileNotFoundError:
            log_queue.put("[ERROR] mpc command not found. Is MPD installed?")
        except subprocess.TimeoutExpired:
            log_queue.put("[ERROR] MPD update timed out after 30 seconds")
        except Exception as e:
            log_queue.put(f"[ERROR] MPD update failed: {str(e)}")
